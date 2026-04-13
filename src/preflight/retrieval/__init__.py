"""
Preflight retrieval module — pgvector hybrid search + per-persona RAG.

Architecture:
- VectorStoreClient protocol → pluggable backends (pgvector primary)
- Hybrid search: dense (semantic) + sparse (BM25 keyword) + FTS (tsvector)
- Per-persona retrieval: each persona's domain keywords scope their own queries
- RRF (Reciprocal Rank Fusion) to merge results from multiple retrieval modes
- Re-ranking via cross-encoder (mxbai-rerank in Phase 2+)
- Query classification: KEYWORD/SEMANTIC/HYBRID with regulatory term detection
- Chunk enrichment: dual keyword/semantic enrichment with ZiRA and NEN context
- DocumentIndex ABC: clean interface for future backend swap (pgvector → Milvus)

Design decisions from ARCHITECTURE.md:
- Phase 1: pgvector only (no Milvus). Supports dense + sparse + FTS in single Postgres
- Per-persona RAG: NOT global retrieval. Each persona gets its own context bundle
- Citation tracking: every retrieved chunk carries its source_id for [§K:source-id] citations
- Data residency: self-hosted models for patient data, cloud APIs only for non-sensitive
"""

from preflight.retrieval.store import (
    VectorStoreClient,
    PgvectorStore,
    PgvectorIndex,
    SearchResult,
    KnowledgeChunk,
)
from preflight.retrieval.retrieve import (
    retrieve_per_persona,
    build_retrieved_context_for_prompt,
    PersonaContext,
    PERSONA_DOMAINS,
)
from preflight.retrieval.classify import classify_query, QueryIntent, ClassifiedQuery
from preflight.retrieval.enrichment import (
    enrich_chunk,
    EnrichedChunk,
    detect_regulatory_references,
    detect_zira_principles,
    REGULATORY_TERMS,
    ZIRA_PRINCIPLES,
)
from preflight.retrieval.reranker import (
    Reranker,
    IdentityReranker,
    HyDEReranker,
    create_reranker,
)
from preflight.retrieval.index import (
    DocumentIndex,
    IndexFilters,
    IndexChunk,
    RetrievalResult,
    QueryIntent as IndexQueryIntent,
    compute_hybrid_score,
)

__all__ = [
    "VectorStoreClient",
    "PgvectorStore",
    "PgvectorIndex",
    "SearchResult",
    "KnowledgeChunk",
    "retrieve_per_persona",
    "build_retrieved_context_for_prompt",
    "PersonaContext",
    "PERSONA_DOMAINS",
    "classify_query",
    "QueryIntent",
    "ClassifiedQuery",
    "enrich_chunk",
    "EnrichedChunk",
    "detect_regulatory_references",
    "detect_zira_principles",
    "REGULATORY_TERMS",
    "ZIRA_PRINCIPLES",
    "Reranker",
    "IdentityReranker",
    "HyDEReranker",
    "create_reranker",
    "DocumentIndex",
    "IndexFilters",
    "IndexChunk",
    "RetrievalResult",
    "IndexQueryIntent",
    "compute_hybrid_score",
]
