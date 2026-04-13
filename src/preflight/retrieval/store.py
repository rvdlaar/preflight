"""
Preflight vector store — pgvector implementation with hybrid search.

Supports:
- Dense vectors (semantic embeddings) via pgvector's vector type
- Sparse vectors (BM25-like keyword matching) via pgvector's sparsevec type
- Full-text search (tsvector) for Dutch/English bilingual queries
- Hybrid search with Reciprocal Rank Fusion (RRF) merging all three
- Per-persona filtering via persona_relevance tags

Phase 1 uses PostgreSQL + pgvector. The VectorStoreClient protocol means
switching to Milvus or another backend is a configuration change, not a code change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from preflight.embedding.client import Vector
from preflight.retrieval.index import (
    DocumentIndex,
    IndexFilters,
    IndexChunk,
    RetrievalResult,
    QueryIntent as IndexQueryIntent,
)


@dataclass
class KnowledgeChunk:
    id: str
    source_id: str
    source_type: str
    title: str
    content: str
    chunk_text: str
    dense_vector: list[float]
    title_vector: list[float] | None = None
    sparse_vector: dict[int, float] | None = None
    language: str = "nl"
    section: str = ""
    page_number: int | None = None
    persona_relevance: list[str] = field(default_factory=list)
    content_type: str = "generic"
    classification: str = "internal"
    context_prefix: str = ""
    enriched_keyword: str = ""
    enriched_semantic: str = ""
    metadata: dict = field(default_factory=dict)
    parent_id: str = ""
    parent_content: str = ""
    chapter_num: int = 0
    chapter_title: str = ""
    versie: str = ""


@dataclass
class SearchResult:
    chunk_id: str
    source_id: str
    source_type: str
    title: str
    content: str
    context_prefix: str = ""
    enriched_keyword: str = ""
    enriched_semantic: str = ""
    score: float = 0.0
    dense_score: float = 0.0
    title_score: float = 0.0
    sparse_score: float = 0.0
    fts_score: float = 0.0
    persona_relevance: list[str] = field(default_factory=list)
    section: str = ""
    metadata: dict = field(default_factory=dict)
    parent_id: str = ""
    parent_content: str = ""
    chapter_num: int = 0
    chapter_title: str = ""
    versie: str = ""


class VectorStoreClient(Protocol):
    async def upsert(self, chunks: list[KnowledgeChunk]) -> list[str]: ...

    async def search(
        self,
        query_vector: Vector,
        query_text: str = "",
        persona_ids: list[str] | None = None,
        content_types: list[str] | None = None,
        source_types: list[str] | None = None,
        top_k: int = 20,
        min_score: float = 0.5,
        alpha: float = 0.5,
    ) -> list[SearchResult]: ...

    async def search_persona(
        self,
        query_vector: Vector,
        query_text: str,
        persona_id: str,
        persona_domains: list[str],
        top_k: int = 15,
        alpha: float = 0.5,
    ) -> list[SearchResult]: ...

    async def delete_by_source(self, source_id: str) -> int: ...

    async def get_stats(self) -> dict: ...


class PgvectorStore:
    """PostgreSQL + pgvector implementation.

    Uses:
    - vector type for dense embeddings (HNSW index)
    - sparsevec type for sparse/BM25 vectors
    - tsvector for full-text search with Dutch/English dictionaries
    - RRF to merge all three retrieval modes
    """

    def __init__(self, database_url: str, expected_dim: int = 384):
        self.database_url = database_url
        self._expected_dim = expected_dim
        self._has_sparsevec: bool = False

    async def _get_conn(self):
        import asyncpg

        return await asyncpg.connect(self.database_url)

    async def ensure_schema(self):
        """Create tables and indexes if they don't exist."""
        conn = await self._get_conn()
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

            try:
                version_row = await conn.fetchrow(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                vector_version = version_row["extversion"] if version_row else "0.0.0"
                self._has_sparsevec = tuple(int(x) for x in vector_version.split(".")[:2]) >= (0, 7)
            except Exception:
                self._has_sparsevec = False

            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS knowledge_chunk (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_id       TEXT NOT NULL,
                    source_type     TEXT NOT NULL DEFAULT 'generic',
                    title           TEXT NOT NULL DEFAULT '',
                    content         TEXT NOT NULL,
                    chunk_text      TEXT NOT NULL,
                    language        TEXT NOT NULL DEFAULT 'nl',
                    section         TEXT DEFAULT '',
                    page_number     INTEGER,
                    persona_relevance TEXT[] DEFAULT '{{}}',
                    content_type    TEXT NOT NULL DEFAULT 'generic',
                    classification  TEXT NOT NULL DEFAULT 'internal',
                    context_prefix  TEXT DEFAULT '',
                    enriched_keyword TEXT DEFAULT '',
                    enriched_semantic TEXT DEFAULT '',
                    metadata        JSONB DEFAULT '{{}}',

                    parent_id       TEXT DEFAULT '',
                    parent_content TEXT DEFAULT '',
                    chapter_num     INTEGER DEFAULT 0,
                    chapter_title  TEXT DEFAULT '',
                    versie         TEXT DEFAULT '',

                    dense_vector   vector({self._expected_dim}),
                    title_vector   vector({self._expected_dim}),

                    content_ts      tsvector,
                    source_file    TEXT DEFAULT '',
                    effective_date DATE,
                    verified       BOOLEAN DEFAULT false,
                    citation_count integer DEFAULT 0,

                    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_dense
                    ON knowledge_chunk USING hnsw (dense_vector vector_cosine_ops)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_title_vec
                    ON knowledge_chunk USING hnsw (title_vector vector_cosine_ops)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_persona
                    ON knowledge_chunk USING gin(persona_relevance)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_fts
                    ON knowledge_chunk USING gin(content_ts)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_source
                    ON knowledge_chunk(source_id)
            """)

            if self._has_sparsevec:
                try:
                    await conn.execute(
                        "ALTER TABLE knowledge_chunk ADD COLUMN IF NOT EXISTS "
                        "sparse_vector sparsevec"
                    )
                except Exception:
                    pass
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_type
                    ON knowledge_chunk(source_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_content_ts
                    ON knowledge_chunk USING gin(content_ts)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_content_type
                    ON knowledge_chunk(content_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_parent
                    ON knowledge_chunk(parent_id) WHERE parent_id != ''
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kc_versie
                    ON knowledge_chunk(versie) WHERE versie != ''
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_source (
                    source_id       TEXT PRIMARY KEY,
                    title           TEXT NOT NULL,
                    source_type     TEXT NOT NULL,
                    language        TEXT NOT NULL DEFAULT 'nl',
                    source_file     TEXT,
                    effective_date  DATE,
                    classification  TEXT DEFAULT 'internal',
                    chunk_count     INTEGER DEFAULT 0,
                    verified        BOOLEAN DEFAULT false,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        finally:
            await conn.close()

    async def upsert(self, chunks: list[KnowledgeChunk]) -> list[str]:
        """Insert or update knowledge chunks. Returns list of chunk IDs."""
        import json as _json

        conn = await self._get_conn()
        ids: list[str] = []
        try:
            for chunk in chunks:
                if not chunk.id:
                    chunk.id = str(uuid.uuid4())

                if chunk.dense_vector:
                    if (
                        self._expected_dim is not None
                        and self._expected_dim > 0
                        and len(chunk.dense_vector) != self._expected_dim
                    ):
                        raise ValueError(
                            f"Vector dimension mismatch: expected {self._expected_dim}, "
                            f"got {len(chunk.dense_vector)} for chunk {chunk.id}. "
                            f"Ensure the embedding model output matches the pgvector column dimension."
                        )
                    vec_str = "[" + ",".join(str(v) for v in chunk.dense_vector) + "]"
                else:
                    vec_str = None

                sparse_str = None
                if chunk.sparse_vector:
                    parts = [f"{k}:{v}" for k, v in sorted(chunk.sparse_vector.items())]
                    sparse_str = "{" + ",".join(parts) + "}"

                persona_list = list(chunk.persona_relevance)

                metadata_json = _json.dumps(chunk.metadata)

                title_vec_str = None
                if chunk.title_vector:
                    title_vec_str = "[" + ",".join(str(v) for v in chunk.title_vector) + "]"

                if self._has_sparsevec and sparse_str:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO knowledge_chunk (
                            id, source_id, source_type, title, content, chunk_text,
                            language, section, page_number, persona_relevance,
                            content_type, classification, context_prefix,
                            enriched_keyword, enriched_semantic, metadata,
                            dense_vector, title_vector, sparse_vector, content_ts,
                            parent_id, parent_content, chapter_num, chapter_title, versie
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb, $17, $18, $19::sparsevec, $20, $21, $22, $23, $24, $25)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            chunk_text = EXCLUDED.chunk_text,
                            dense_vector = EXCLUDED.dense_vector,
                            title_vector = EXCLUDED.title_vector,
                            sparse_vector = EXCLUDED.sparse_vector,
                            context_prefix = EXCLUDED.context_prefix,
                            enriched_keyword = EXCLUDED.enriched_keyword,
                            enriched_semantic = EXCLUDED.enriched_semantic,
                            metadata = EXCLUDED.metadata,
                            parent_id = EXCLUDED.parent_id,
                            parent_content = EXCLUDED.parent_content,
                            chapter_num = EXCLUDED.chapter_num,
                            chapter_title = EXCLUDED.chapter_title,
                            versie = EXCLUDED.versie,
                            updated_at = now()
                        RETURNING id::text
                        """,
                        chunk.id,
                        chunk.source_id,
                        chunk.source_type,
                        chunk.title,
                        chunk.content,
                        chunk.chunk_text,
                        chunk.language,
                        chunk.section,
                        chunk.page_number,
                        persona_list,
                        chunk.content_type,
                        chunk.classification,
                        chunk.context_prefix,
                        chunk.enriched_keyword,
                        chunk.enriched_semantic,
                        metadata_json,
                        vec_str,
                        title_vec_str,
                        sparse_str,
                        None,
                        chunk.parent_id,
                        chunk.parent_content,
                        chunk.chapter_num,
                        chunk.chapter_title,
                        chunk.versie,
                    )
                else:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO knowledge_chunk (
                            id, source_id, source_type, title, content, chunk_text,
                            language, section, page_number, persona_relevance,
                            content_type, classification, context_prefix,
                            enriched_keyword, enriched_semantic, metadata,
                            dense_vector, title_vector, content_ts,
                            parent_id, parent_content, chapter_num, chapter_title, versie
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb, $17, $18, $19, $20, $21, $22, $23, $24)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            chunk_text = EXCLUDED.chunk_text,
                            dense_vector = EXCLUDED.dense_vector,
                            title_vector = EXCLUDED.title_vector,
                            context_prefix = EXCLUDED.context_prefix,
                            enriched_keyword = EXCLUDED.enriched_keyword,
                            enriched_semantic = EXCLUDED.enriched_semantic,
                            metadata = EXCLUDED.metadata,
                            parent_id = EXCLUDED.parent_id,
                            parent_content = EXCLUDED.parent_content,
                            chapter_num = EXCLUDED.chapter_num,
                            chapter_title = EXCLUDED.chapter_title,
                            versie = EXCLUDED.versie,
                            updated_at = now()
                        RETURNING id::text
                        """,
                        chunk.id,
                        chunk.source_id,
                        chunk.source_type,
                        chunk.title,
                        chunk.content,
                        chunk.chunk_text,
                        chunk.language,
                        chunk.section,
                        chunk.page_number,
                        persona_list,
                        chunk.content_type,
                        chunk.classification,
                        chunk.context_prefix,
                        chunk.enriched_keyword,
                        chunk.enriched_semantic,
                        metadata_json,
                        vec_str,
                        title_vec_str,
                        None,
                        chunk.parent_id,
                        chunk.parent_content,
                        chunk.chapter_num,
                        chunk.chapter_title,
                        chunk.versie,
                    )

                chunk_id = row["id"]

                text_for_ts = f"{chunk.content} {chunk.context_prefix}"
                if chunk.enriched_keyword:
                    text_for_ts = f"{chunk.enriched_keyword} {text_for_ts}"
                if chunk.title:
                    text_for_ts = f"{chunk.title} {text_for_ts}"
                await conn.execute(
                    """
                    UPDATE knowledge_chunk SET content_ts =
                        setweight(to_tsvector('dutch', $1), 'B') ||
                        setweight(to_tsvector('english', $1), 'C')
                    WHERE id = $2::uuid
                    """,
                    text_for_ts,
                    chunk_id,
                )

            source_ids = set(c.source_id for c in chunks)
            for sid in source_ids:
                source_chunks = [c for c in chunks if c.source_id == sid]
                await conn.execute(
                    """
                    INSERT INTO knowledge_source (source_id, title, source_type, language, classification, chunk_count)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (source_id) DO UPDATE SET
                        chunk_count = EXCLUDED.chunk_count,
                        updated_at = now()
                    """,
                    sid,
                    source_chunks[0].title,
                    source_chunks[0].source_type,
                    source_chunks[0].language,
                    source_chunks[0].classification,
                    len(source_chunks),
                )
        finally:
            await conn.close()
        return ids

    async def search(
        self,
        query_vector: Vector,
        query_text: str = "",
        persona_ids: list[str] | None = None,
        content_types: list[str] | None = None,
        source_types: list[str] | None = None,
        top_k: int = 20,
        min_score: float = 0.5,
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        """Hybrid search: dense + title + FTS with alpha-blended RRF merging."""
        conn = await self._get_conn()
        try:
            results = await self._hybrid_search(
                conn,
                query_vector,
                query_text,
                persona_ids,
                content_types,
                source_types,
                top_k,
                min_score,
                alpha=alpha,
            )
        finally:
            await conn.close()
        return results

    async def search_persona(
        self,
        query_vector: Vector,
        query_text: str,
        persona_id: str,
        persona_domains: list[str],
        top_k: int = 15,
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        """Per-persona retrieval — core of Preflight's RAG.

        Each persona's domain keywords become query augmentation.
        Results are filtered to persona-relevant chunks AND domain-matched.
        Alpha controls dense/keyword balance (from query classifier).
        """
        domain_terms = " ".join(persona_domains)

        augmented_query = f"{query_text} {domain_terms}"

        conn = await self._get_conn()
        try:
            results = await self._hybrid_search(
                conn,
                query_vector,
                augmented_query,
                persona_ids=[persona_id],
                top_k=top_k,
                min_score=0.3,
                alpha=alpha,
            )
        finally:
            await conn.close()

        for r in results:
            if r.persona_relevance and persona_id not in r.persona_relevance:
                r.score *= 0.7

        return results

    async def _hybrid_search(
        self,
        conn,
        query_vector: Vector,
        query_text: str,
        persona_ids: list[str] | None,
        content_types: list[str] | None,
        source_types: list[str] | None,
        top_k: int,
        min_score: float,
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        """Execute hybrid search combining dense, title, and FTS with alpha-blended RRF."""
        vec_str = "[" + ",".join(str(v) for v in query_vector.dense) + "]"

        fetch_k = top_k * 5

        filter_conditions: list[str] = []
        filter_params: list = []

        if persona_ids:
            persona_list = "{" + ",".join(f'"{p}"' for p in persona_ids) + "}"
            filter_conditions.append("k.persona_relevance && $1::text[]")
            filter_params.append(persona_list)

        if content_types:
            type_arr = "{" + ",".join(f'"{t}"' for t in content_types) + "}"
            filter_conditions.append("k.content_type = ANY($2::text[])")
            filter_params.append(type_arr)

        if source_types:
            stype_arr = "{" + ",".join(f'"{t}"' for t in source_types) + "}"
            filter_conditions.append("k.source_type = ANY($3::text[])")
            filter_params.append(stype_arr)

        filter_where = ""
        if filter_conditions:
            filter_where = "AND " + " AND ".join(filter_conditions)

        dense_sql = f"""
            SELECT k.id::text, k.source_id, k.source_type, k.title,
                   k.content, k.context_prefix, k.section, k.persona_relevance,
                   k.metadata, k.enriched_keyword, k.enriched_semantic,
                   k.parent_id, k.parent_content, k.chapter_num, k.chapter_title, k.versie,
                   1 - (k.dense_vector <=> $1::vector) AS dense_score
            FROM knowledge_chunk k
            WHERE k.dense_vector IS NOT NULL {filter_where}
            ORDER BY k.dense_vector <=> $1::vector
            LIMIT {fetch_k}
        """
        dense_params = [vec_str] + filter_params

        title_sql = f"""
            SELECT k.id::text, k.source_id, k.source_type, k.title,
                   k.content, k.context_prefix, k.section, k.persona_relevance,
                   k.metadata, k.enriched_keyword, k.enriched_semantic,
                   k.parent_id, k.parent_content, k.chapter_num, k.chapter_title, k.versie,
                   1 - (k.title_vector <=> $1::vector) AS title_score
            FROM knowledge_chunk k
            WHERE k.title_vector IS NOT NULL {filter_where}
            ORDER BY k.title_vector <=> $1::vector
            LIMIT {fetch_k}
        """
        title_params = [vec_str] + filter_params

        fts_sql = None
        fts_params = None
        if query_text.strip():
            fts_sql = f"""
                SELECT k.id::text, k.source_id, k.source_type, k.title,
                       k.content, k.context_prefix, k.section, k.persona_relevance,
                       k.metadata, k.enriched_keyword, k.enriched_semantic,
                       k.parent_id, k.parent_content, k.chapter_num, k.chapter_title, k.versie,
                       ts_rank_cd(k.content_ts, query) AS fts_score
                FROM knowledge_chunk k, plainto_tsquery('dutch', $1) AS query
                WHERE k.content_ts @@ query {filter_where}
                ORDER BY fts_score DESC
                LIMIT {fetch_k}
            """
            fts_params = [query_text] + filter_params

        dense_rows = await conn.fetch(dense_sql, *dense_params)
        title_rows = await conn.fetch(title_sql, *title_params)

        fts_rows = []
        if fts_sql and fts_params:
            fts_rows = await conn.fetch(fts_sql, *fts_params)

        results = self._rrf_merge(
            dense_rows, fts_rows, top_k, min_score, title_rows=title_rows, alpha=alpha
        )
        return results

    def _rrf_merge(
        self,
        dense_rows: list,
        fts_rows: list,
        top_k: int,
        min_score: float,
        k: int = 60,
        title_rows: list | None = None,
        alpha: float = 0.5,
        title_ratio: float = 0.1,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion to merge dense, title, and FTS results.

        Alpha blending: alpha controls dense vs keyword balance.
        alpha=1.0 → pure dense, alpha=0.0 → pure keyword (FTS).
        Title rows contribute via title_ratio weighting.

        RRF score = alpha * (dense_weight * 1/(k+rank+1) + title_weight * 1/(k+rank+1))
                   + (1-alpha) * 1/(k+rank+1) for keyword/FTS
        """
        scores: dict[str, dict] = {}

        for rank, row in enumerate(dense_rows):
            cid = row["id"]
            if cid not in scores:
                scores[cid] = {
                    "source_id": row["source_id"],
                    "source_type": row["source_type"],
                    "title": row["title"],
                    "content": row["content"],
                    "context_prefix": row.get("context_prefix", ""),
                    "enriched_keyword": row.get("enriched_keyword", ""),
                    "enriched_semantic": row.get("enriched_semantic", ""),
                    "section": row.get("section", ""),
                    "persona_relevance": row.get("persona_relevance", []),
                    "metadata": row.get("metadata", {}),
                    "parent_id": row.get("parent_id", ""),
                    "parent_content": row.get("parent_content", ""),
                    "chapter_num": row.get("chapter_num", 0),
                    "chapter_title": row.get("chapter_title", ""),
                    "versie": row.get("versie", ""),
                    "rrf_score": 0.0,
                    "dense_score": float(row.get("dense_score", 0)),
                    "title_score": 0.0,
                    "fts_score": 0.0,
                }
            scores[cid]["rrf_score"] += alpha * (1 - title_ratio) / (k + rank + 1)
            scores[cid]["dense_score"] = float(row.get("dense_score", 0))

        if title_rows:
            for rank, row in enumerate(title_rows):
                cid = row["id"]
                if cid not in scores:
                    scores[cid] = {
                        "source_id": row["source_id"],
                        "source_type": row["source_type"],
                        "title": row["title"],
                        "content": row["content"],
                        "context_prefix": row.get("context_prefix", ""),
                        "enriched_keyword": row.get("enriched_keyword", ""),
                        "enriched_semantic": row.get("enriched_semantic", ""),
                        "section": row.get("section", ""),
                        "persona_relevance": row.get("persona_relevance", []),
                        "metadata": row.get("metadata", {}),
                        "parent_id": row.get("parent_id", ""),
                        "parent_content": row.get("parent_content", ""),
                        "chapter_num": row.get("chapter_num", 0),
                        "chapter_title": row.get("chapter_title", ""),
                        "versie": row.get("versie", ""),
                        "rrf_score": 0.0,
                        "dense_score": 0.0,
                        "title_score": float(row.get("title_score", 0)),
                        "fts_score": 0.0,
                    }
                scores[cid]["rrf_score"] += alpha * title_ratio / (k + rank + 1)
                scores[cid]["title_score"] = float(row.get("title_score", 0))

        for rank, row in enumerate(fts_rows):
            cid = row["id"]
            if cid not in scores:
                scores[cid] = {
                    "source_id": row["source_id"],
                    "source_type": row["source_type"],
                    "title": row["title"],
                    "content": row["content"],
                    "context_prefix": row.get("context_prefix", ""),
                    "enriched_keyword": row.get("enriched_keyword", ""),
                    "enriched_semantic": row.get("enriched_semantic", ""),
                    "section": row.get("section", ""),
                    "persona_relevance": row.get("persona_relevance", []),
                    "metadata": row.get("metadata", {}),
                    "parent_id": row.get("parent_id", ""),
                    "parent_content": row.get("parent_content", ""),
                    "chapter_num": row.get("chapter_num", 0),
                    "chapter_title": row.get("chapter_title", ""),
                    "versie": row.get("versie", ""),
                    "rrf_score": 0.0,
                    "dense_score": 0.0,
                    "title_score": 0.0,
                    "fts_score": float(row.get("fts_score", 0)),
                }
            scores[cid]["rrf_score"] += (1 - alpha) / (k + rank + 1)
            scores[cid]["fts_score"] = float(row.get("fts_score", 0))

        results = []
        for cid, data in sorted(scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)[
            :top_k
        ]:
            if data["rrf_score"] < min_score / (k + 1):
                continue

            pr = data.get("persona_relevance", [])
            if isinstance(pr, str):
                pr = [p.strip('"') for p in pr.strip("{}").split(",") if p.strip()]

            results.append(
                SearchResult(
                    chunk_id=cid,
                    source_id=data["source_id"],
                    source_type=data["source_type"],
                    title=data["title"],
                    content=data["content"],
                    context_prefix=data.get("context_prefix", ""),
                    enriched_keyword=data.get("enriched_keyword", ""),
                    enriched_semantic=data.get("enriched_semantic", ""),
                    score=data["rrf_score"],
                    dense_score=data["dense_score"],
                    title_score=data.get("title_score", 0.0),
                    fts_score=data["fts_score"],
                    persona_relevance=pr,
                    section=data.get("section", ""),
                    metadata=data.get("metadata", {}),
                    parent_id=data.get("parent_id", ""),
                    parent_content=data.get("parent_content", ""),
                    chapter_num=data.get("chapter_num", 0),
                    chapter_title=data.get("chapter_title", ""),
                    versie=data.get("versie", ""),
                )
            )

        return results

    async def delete_by_source(self, source_id: str) -> int:
        """Delete all chunks for a source (for re-ingestion)."""
        conn = await self._get_conn()
        try:
            result = await conn.execute(
                "DELETE FROM knowledge_chunk WHERE source_id = $1", source_id
            )
            await conn.execute("DELETE FROM knowledge_source WHERE source_id = $1", source_id)
            count = int(result.split()[-1]) if result else 0
        finally:
            await conn.close()
        return count

    async def get_stats(self) -> dict:
        """Return knowledge base statistics."""
        conn = await self._get_conn()
        try:
            total = await conn.fetchval("SELECT count(*) FROM knowledge_chunk")
            sources = await conn.fetchval("SELECT count(*) FROM knowledge_source")
            types = await conn.fetch(
                "SELECT source_type, count(*) as cnt FROM knowledge_chunk GROUP BY source_type"
            )
            personas = await conn.fetch(
                "SELECT unnest(persona_relevance) as p, count(*) as cnt FROM knowledge_chunk GROUP BY p ORDER BY cnt DESC"
            )
        finally:
            await conn.close()

        return {
            "total_chunks": total or 0,
            "total_sources": sources or 0,
            "by_type": {r["source_type"]: r["cnt"] for r in types},
            "by_persona": {r["p"]: r["cnt"] for r in personas},
        }


class MemoryStore:
    """In-memory vector store for testing and local dev.

    Uses hybrid search: cosine similarity (dense) + TF-IDF keyword matching.
    RRF merges both signals, mirroring PgvectorStore's hybrid approach.
    """

    def __init__(self):
        self._chunks: dict[str, KnowledgeChunk] = {}
        self._tf_index: dict[str, dict[str, int]] = {}
        self._doc_freq: dict[str, int] = {}
        self._idf_cache: dict[str, float] = {}
        self._index_dirty = True

    def _rebuild_index(self) -> None:
        import math
        from collections import Counter

        self._tf_index = {}
        self._doc_freq = Counter()
        for cid, chunk in self._chunks.items():
            tokens = self._tokenize(
                chunk.content
                + " "
                + chunk.title
                + " "
                + chunk.chunk_text
                + " "
                + chunk.section
                + " "
                + chunk.chapter_title
            )
            tf = Counter(tokens)
            self._tf_index[cid] = dict(tf)
            for term in set(tokens):
                self._doc_freq[term] += 1

        n = len(self._chunks) or 1
        self._idf_cache = {}
        for term, df in self._doc_freq.items():
            self._idf_cache[term] = math.log((n + 1) / (df + 1)) + 1

        self._index_dirty = False

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re

        return re.findall(r"\w+", text.lower())

    def _tfidf_score(self, query: str, chunk_id: str) -> float:
        if self._index_dirty:
            self._rebuild_index()

        query_tokens = self._tokenize(query)
        if not query_tokens or chunk_id not in self._tf_index:
            return 0.0

        tf = self._tf_index.get(chunk_id, {})
        max_tf = max(tf.values()) if tf else 1
        score = 0.0
        for qt in query_tokens:
            if qt in tf and qt in self._idf_cache:
                tf_norm = tf[qt] / max_tf
                score += tf_norm * self._idf_cache[qt]
        return score

    async def upsert(self, chunks: list[KnowledgeChunk]) -> list[str]:
        ids = []
        for chunk in chunks:
            if not chunk.id:
                chunk.id = str(uuid.uuid4())
            self._chunks[chunk.id] = chunk
            ids.append(chunk.id)
        self._index_dirty = True
        return ids

    async def search(
        self,
        query_vector: Vector,
        query_text: str = "",
        persona_ids: list[str] | None = None,
        content_types: list[str] | None = None,
        source_types: list[str] | None = None,
        top_k: int = 20,
        min_score: float = 0.5,
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        import math

        if self._index_dirty:
            self._rebuild_index()

        candidates: dict[str, dict] = {}
        k = 60

        has_dense = query_vector.dense and len(query_vector.dense) > 1
        q_norm = math.sqrt(sum(v * v for v in query_vector.dense)) if has_dense else 0.0

        if has_dense and q_norm > 0:
            dense_scores: list[tuple[float, KnowledgeChunk]] = []
            for chunk in self._chunks.values():
                if not chunk.dense_vector or len(chunk.dense_vector) < 2:
                    continue
                if persona_ids and not any(p in chunk.persona_relevance for p in persona_ids):
                    continue
                if content_types and chunk.content_type not in content_types:
                    continue
                if source_types and chunk.source_type not in source_types:
                    continue
                dot = sum(a * b for a, b in zip(query_vector.dense, chunk.dense_vector))
                c_norm = math.sqrt(sum(v * v for v in chunk.dense_vector))
                if c_norm == 0:
                    continue
                cosine = dot / (q_norm * c_norm)
                dense_scores.append((cosine, chunk))

            dense_scores.sort(key=lambda x: x[0], reverse=True)
            for rank, (score, chunk) in enumerate(dense_scores[: top_k * 3]):
                rrf = alpha / (k + rank + 1)
                if chunk.id not in candidates:
                    candidates[chunk.id] = {"chunk": chunk, "rrf": 0.0, "dense": 0.0, "tfidf": 0.0}
                candidates[chunk.id]["rrf"] += rrf
                candidates[chunk.id]["dense"] = score

        if query_text.strip():
            tfidf_scores: list[tuple[float, KnowledgeChunk]] = []
            for chunk in self._chunks.values():
                if persona_ids and not any(p in chunk.persona_relevance for p in persona_ids):
                    continue
                if content_types and chunk.content_type not in content_types:
                    continue
                if source_types and chunk.source_type not in source_types:
                    continue
                score = self._tfidf_score(query_text, chunk.id)
                if score > 0:
                    tfidf_scores.append((score, chunk))

            tfidf_scores.sort(key=lambda x: x[0], reverse=True)
            for rank, (score, chunk) in enumerate(tfidf_scores[: top_k * 3]):
                rrf = (1 - alpha) / (k + rank + 1)
                if chunk.id not in candidates:
                    candidates[chunk.id] = {"chunk": chunk, "rrf": 0.0, "dense": 0.0, "tfidf": 0.0}
                candidates[chunk.id]["rrf"] += rrf
                candidates[chunk.id]["tfidf"] = score

        ranked = sorted(candidates.values(), key=lambda x: x["rrf"], reverse=True)

        results = []
        for entry in ranked[:top_k]:
            chunk = entry["chunk"]
            results.append(
                SearchResult(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    source_type=chunk.source_type,
                    title=chunk.title,
                    content=chunk.content,
                    context_prefix=chunk.context_prefix,
                    enriched_keyword=chunk.enriched_keyword,
                    enriched_semantic=chunk.enriched_semantic,
                    score=entry["rrf"],
                    dense_score=entry["dense"],
                    fts_score=entry["tfidf"],
                    persona_relevance=chunk.persona_relevance,
                    section=chunk.section,
                    metadata=chunk.metadata,
                    parent_id=chunk.parent_id,
                    parent_content=chunk.parent_content,
                    chapter_num=chunk.chapter_num,
                    chapter_title=chunk.chapter_title,
                    versie=chunk.versie,
                )
            )
        return results

    async def search_persona(
        self,
        query_vector: Vector,
        query_text: str,
        persona_id: str,
        persona_domains: list[str],
        top_k: int = 15,
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        return await self.search(query_vector, query_text, persona_ids=[persona_id], top_k=top_k)

    async def delete_by_source(self, source_id: str) -> int:
        to_delete = [cid for cid, c in self._chunks.items() if c.source_id == source_id]
        for cid in to_delete:
            del self._chunks[cid]
        return len(to_delete)

    async def get_stats(self) -> dict:
        by_type: dict[str, int] = {}
        by_persona: dict[str, int] = {}
        for chunk in self._chunks.values():
            by_type[chunk.source_type] = by_type.get(chunk.source_type, 0) + 1
            for p in chunk.persona_relevance:
                by_persona[p] = by_persona.get(p, 0) + 1
        return {
            "total_chunks": len(self._chunks),
            "total_sources": len(set(c.source_id for c in self._chunks.values())),
            "by_type": by_type,
            "by_persona": by_persona,
        }


_GLOBAL_STORE: VectorStoreClient | None = None
_STORE_BACKEND: str = "memory"
_STORE_DATABASE_URL: str = ""
_STORE_DIM: int = 384


def configure_store(
    backend: str = "memory",
    database_url: str = "",
    expected_dim: int = 384,
) -> None:
    global _STORE_BACKEND, _STORE_DATABASE_URL, _STORE_DIM
    _STORE_BACKEND = backend
    _STORE_DATABASE_URL = database_url
    _STORE_DIM = expected_dim
    reset_global_store()


def get_global_store() -> VectorStoreClient:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        if _STORE_BACKEND == "pgvector" and _STORE_DATABASE_URL:
            _GLOBAL_STORE = PgvectorStore(_STORE_DATABASE_URL, expected_dim=_STORE_DIM)
        else:
            _GLOBAL_STORE = MemoryStore()
    return _GLOBAL_STORE


def reset_global_store() -> None:
    global _GLOBAL_STORE
    _GLOBAL_STORE = None


_CHUNK_UPDATEABLE_COLUMNS = frozenset(
    {
        "title",
        "content",
        "chunk_text",
        "context_prefix",
        "language",
        "section",
        "page_number",
        "persona_relevance",
        "content_type",
        "classification",
        "enriched_keyword",
        "enriched_semantic",
        "metadata",
    }
)


class PgvectorIndex:
    """DocumentIndex adapter over PgvectorStore.

    Implements the DocumentIndex protocol so the pipeline can call
    hybrid_retrieval() without knowing the backend is pgvector.
    This is the Phase 1 implementation — Phase 2 swaps in MilvusIndex.
    """

    def __init__(self, store: PgvectorStore):
        self._store = store

    async def hybrid_retrieval(
        self,
        query_vector: list[float],
        query_text: str,
        alpha: float = 0.5,
        filters: IndexFilters | None = None,
        top_k: int = 15,
        intent: IndexQueryIntent = IndexQueryIntent.HYBRID,
    ) -> list[RetrievalResult]:
        f = filters or IndexFilters()
        results = await self._store.search(
            query_vector=Vector(dense=query_vector),
            query_text=query_text,
            persona_ids=f.persona_ids or None,
            content_types=f.content_types or None,
            source_types=f.source_types or None,
            top_k=top_k,
            min_score=0.3,
            alpha=alpha,
        )
        return [
            RetrievalResult(
                chunk_id=r.chunk_id,
                document_id=r.source_id,
                title=r.title,
                content=r.content,
                context_prefix=r.context_prefix,
                enriched_keyword=r.enriched_keyword,
                enriched_semantic=r.enriched_semantic,
                score=r.score,
                dense_score=r.dense_score,
                fts_score=r.fts_score,
                title_score=r.title_score,
                persona_relevance=r.persona_relevance,
                section=r.section,
                metadata=r.metadata,
                source_id=r.source_id,
            )
            for r in results
        ]

    async def index(self, chunks: list[IndexChunk]) -> list[str]:
        kc_list = []
        for c in chunks:
            kc_list.append(
                KnowledgeChunk(
                    id=c.chunk_id,
                    source_id=c.document_id,
                    source_type=c.source_type,
                    title=c.title,
                    content=c.content,
                    chunk_text=c.content,
                    dense_vector=c.dense_vector,
                    title_vector=c.title_vector,
                    sparse_vector=c.sparse_vector,
                    language=c.language,
                    section=c.section,
                    page_number=c.page_number,
                    persona_relevance=c.persona_relevance,
                    content_type=c.content_type,
                    classification="internal",
                    context_prefix=c.context_prefix,
                    metadata=c.metadata if isinstance(c.metadata, dict) else {},
                )
            )
        return await self._store.upsert(kc_list)

    async def update_single(self, document_id: str, fields: dict) -> None:
        conn = await self._store._get_conn()
        try:
            sets = []
            params = []
            idx = 1
            for key, val in fields.items():
                if key not in _CHUNK_UPDATEABLE_COLUMNS:
                    continue
                sets.append(f"{key} = ${idx}")
                params.append(val)
                idx += 1
            if not sets:
                return
            sets.append("updated_at = now()")
            params.append(document_id)
            await conn.execute(
                f"UPDATE knowledge_chunk SET {', '.join(sets)} WHERE source_id = ${idx}",
                *params,
            )
        finally:
            await conn.close()

    async def delete_single(self, document_id: str) -> int:
        return await self._store.delete_by_source(document_id)
