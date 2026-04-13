"""
Preflight DocumentIndex ABC — clean abstraction for vector store backends.

FIRST PRINCIPLE: Phase 1 uses pgvector. Phase 2 migrates to Milvus. The search
pipeline must never know which backend is running. This ABC defines the contract.

SECOND ORDER: If we leak pgvector-specific SQL into the pipeline, migration
requires rewriting search logic. Solution: all backend-specific code stays
behind this interface. The pipeline calls hybrid_retrieval(), not SQL.

INVERSION: What makes an abstraction fail? Too many methods. Solution: minimal
interface — 4 methods for Phase 1, extend as needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence


class QueryIntent(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class IndexFilters:
    persona_ids: list[str] = field(default_factory=list)
    content_types: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    access_control_list: list[str] = field(default_factory=list)
    language: str = "nl"
    versie: str = ""
    parent_expansion: bool = True


@dataclass
class IndexChunk:
    chunk_id: str
    document_id: str
    title: str
    content: str
    dense_vector: list[float] = field(default_factory=list)
    title_vector: list[float] = field(default_factory=list)
    sparse_vector: dict[int, float] | None = None
    language: str = "nl"
    section: str = ""
    page_number: int | None = None
    persona_relevance: list[str] = field(default_factory=list)
    content_type: str = "generic"
    source_type: str = "regulation"
    source_id: str = ""
    context_prefix: str = ""
    metadata: dict = field(default_factory=dict)
    parent_id: str = ""
    parent_content: str = ""
    chapter_num: int = 0
    chapter_title: str = ""
    versie: str = ""


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    title: str
    content: str
    context_prefix: str = ""
    enriched_keyword: str = ""
    enriched_semantic: str = ""
    score: float = 0.0
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fts_score: float = 0.0
    title_score: float = 0.0
    persona_relevance: list[str] = field(default_factory=list)
    section: str = ""
    metadata: dict = field(default_factory=dict)
    source_id: str = ""
    parent_id: str = ""
    parent_content: str = ""
    chapter_num: int = 0
    chapter_title: str = ""
    versie: str = ""


class DocumentIndex(Protocol):
    """Abstract interface for vector store backends.

    Implementations: PgvectorIndex (Phase 1), MilvusIndex (Phase 2+).
    """

    async def hybrid_retrieval(
        self,
        query_vector: list[float],
        query_text: str,
        alpha: float = 0.5,
        filters: IndexFilters | None = None,
        top_k: int = 15,
        intent: QueryIntent = QueryIntent.HYBRID,
    ) -> list[RetrievalResult]: ...

    async def index(self, chunks: list[IndexChunk]) -> list[str]: ...

    async def update_single(self, document_id: str, fields: dict) -> None: ...

    async def delete_single(self, document_id: str) -> int: ...


def compute_hybrid_score(
    dense_score: float,
    sparse_score: float,
    fts_score: float,
    alpha: float = 0.5,
    title_ratio: float = 0.1,
    title_dense_score: float = 0.0,
) -> float:
    """Compute combined hybrid score using Onyx-style alpha blending.

    alpha=1.0 → pure dense vector
    alpha=0.0 → pure keyword (sparse + FTS)
    alpha=0.5 → balanced blend (default)

    title_ratio controls how much the title embedding contributes.
    """
    vector_score = (title_ratio * title_dense_score) + ((1 - title_ratio) * dense_score)
    keyword_score = max(sparse_score, fts_score)
    return alpha * vector_score + (1 - alpha) * keyword_score
