"""
Preflight embedding pipeline — end-to-end from document to pgvector.

Orchestrates: parse → chunk → contextualize → embed → store

This is the ingestion pipeline called by `preflight ingest`.
Each step is pluggable: swap chunkers, embedding models, or vector stores
without changing the pipeline logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from preflight.embedding.client import (
    EmbeddingRouter,
    Vector,
)
from preflight.embedding.chunking import (
    Chunk,
    chunk_text,
    chunk_archimate_elements,
    chunk_tabular,
)
from preflight.embedding.chunking import chunk_text_semantic
from preflight.embedding.contextual import (
    contextualize_chunks,
    ContextGenerator,
    StaticContextGenerator,
    ContextualizedChunk,
)
from preflight.embedding.parent_child import parent_child_chunk

logger = logging.getLogger(__name__)


@dataclass
class IngestedDocument:
    source_id: str
    source_file: str
    content_type: str
    language: str
    title: str
    chunks: list[Chunk] = field(default_factory=list)
    contextualized: list[ContextualizedChunk] = field(default_factory=list)
    vectors: list[Vector] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parent_sections: list = field(default_factory=list)


@dataclass
class IngestResult:
    documents: list[IngestedDocument] = field(default_factory=list)
    total_chunks: int = 0
    total_vectors: int = 0
    errors: list[str] = field(default_factory=list)


async def ingest_document(
    text: str,
    content_type: str,
    source_id: str,
    source_file: str = "",
    title: str = "",
    language: str = "nl",
    metadata: dict | None = None,
    embedding_router: EmbeddingRouter | None = None,
    context_generator: ContextGenerator | None = None,
    archimate_elements: list[dict] | None = None,
    archimate_relationships: list[dict] | None = None,
    tabular_rows: list[str] | None = None,
    tabular_headers: list[str] | None = None,
    use_parent_child: bool = True,
    child_chunk_size: int = 512,
    child_overlap: int = 77,
) -> IngestedDocument:
    """Ingest a single document through the full pipeline.

    Steps:
    1. Chunk by content type (parent/child for section-aware documents)
    2. Add contextual prefixes (Anthropic-style contextual retrieval)
    3. Embed all contextualized chunks
    4. Return IngestedDocument ready for storage

    For ArchiMate: pass elements/relationships instead of text.
    For tabular: pass rows/headers instead of text.
    For regulatory/policy: parent/child chunking preserves section structure.
    """
    doc = IngestedDocument(
        source_id=source_id,
        source_file=source_file,
        content_type=content_type,
        language=language,
        title=title or source_file,
    )

    meta = metadata or {}
    meta = {**meta}
    meta.setdefault("source_id", source_id)
    meta.setdefault("doc_title", title or source_file)
    meta.setdefault("language", language)

    if content_type == "archimate" and archimate_elements is not None:
        doc.chunks = chunk_archimate_elements(archimate_elements, archimate_relationships or [])
    elif content_type == "tabular" and tabular_rows is not None:
        doc.chunks = chunk_tabular(
            tabular_rows,
            tabular_headers or [],
            source_id=source_id,
            metadata=meta,
        )
    elif use_parent_child and content_type in ("regulatory", "policy"):
        parents, children = parent_child_chunk(
            text,
            content_type=content_type,
            metadata=meta,
            child_size=child_chunk_size,
            child_overlap=child_overlap,
            table_intact=True,
        )
        doc.chunks = children
        doc.parent_sections = parents
        parent_by_id = {p.id: p for p in parents}
        for chunk in doc.chunks:
            if hasattr(chunk, "parent_id") and chunk.parent_id and chunk.parent_id in parent_by_id:
                parent = parent_by_id[chunk.parent_id]
                chunk.metadata["parent_content"] = parent.text
    else:
        try:
            doc.chunks = chunk_text_semantic(text, content_type, metadata=meta)
        except Exception:
            doc.chunks = chunk_text(text, content_type, metadata=meta)

    if not doc.chunks:
        doc.errors.append(f"No chunks produced from {source_id}")
        return doc

    generator = context_generator or StaticContextGenerator()

    chunk_texts = [c.text for c in doc.chunks]
    chunk_metas = [c.metadata for c in doc.chunks]

    doc.contextualized = await contextualize_chunks(
        chunks=chunk_texts,
        content_type=content_type,
        metadata_list=chunk_metas,
        generator=generator,
        source_id=source_id,
    )

    if embedding_router:
        full_texts = [c.full_text for c in doc.contextualized]
        try:
            result = await embedding_router.embed_for_type(full_texts, content_type)
            doc.vectors = result.vectors
            if len(doc.vectors) != len(doc.contextualized):
                doc.errors.append(
                    f"Embedding count mismatch: {len(doc.vectors)} vectors "
                    f"for {len(doc.contextualized)} chunks"
                )
        except Exception as e:
            doc.errors.append(f"Embedding failed: {e}")
    else:
        doc.vectors = [
            Vector(dense=vec.dense) if vec and vec.dense else Vector(dense=[])
            for vec in doc.contextualized
        ] or [Vector(dense=[]) for _ in doc.contextualized]

    return doc


async def ingest_batch(
    documents: list[dict],
    embedding_router: EmbeddingRouter | None = None,
    context_generator: ContextGenerator | None = None,
) -> IngestResult:
    """Ingest a batch of documents.

    Each document dict should have:
      text, content_type, source_id, source_file, title, language, metadata
    Plus optional archimate_elements/relationships or tabular_rows/headers.
    """
    result = IngestResult()

    for doc_spec in documents:
        try:
            ingested = await ingest_document(
                text=doc_spec.get("text", ""),
                content_type=doc_spec.get("content_type", "generic"),
                source_id=doc_spec.get("source_id", ""),
                source_file=doc_spec.get("source_file", ""),
                title=doc_spec.get("title", ""),
                language=doc_spec.get("language", "nl"),
                metadata=doc_spec.get("metadata"),
                embedding_router=embedding_router,
                context_generator=context_generator,
                archimate_elements=doc_spec.get("archimate_elements"),
                archimate_relationships=doc_spec.get("archimate_relationships"),
                tabular_rows=doc_spec.get("tabular_rows"),
                tabular_headers=doc_spec.get("tabular_headers"),
            )
            result.documents.append(ingested)
            result.total_chunks += len(ingested.chunks)
            result.total_vectors += len(ingested.vectors)
            result.errors.extend(ingested.errors)
        except Exception as e:
            result.errors.append(f"Failed to ingest {doc_spec.get('source_id', '?')}: {e}")

    return result
