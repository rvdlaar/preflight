"""
Preflight reranker — cross-encoder reranking for per-persona retrieval.

The single highest-ROI RAG improvement (Anthropic research): combining BM25 +
dense retrieval + reranking reduces failure rate by 67%.

Architecture:
  1. pgvector retrieves top-150 candidates (dense + sparse + FTS + RRF)
  2. Cross-encoder reranks top-150 → top-20 per persona
  3. Reranker sees the FULL query-document pair, not just embeddings

Protocol-based: MXBAI implementation when sentence-transformers is available,
fallback to identity (no reranking) when it's not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from preflight.retrieval.store import SearchResult


class Reranker(Protocol):
    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 20
    ) -> list[SearchResult]: ...


class MXBAIReranker:
    """mxbai-rerank-large-v2: 100+ languages (including Dutch), 8K context.

    The best multilingual cross-encoder available. Critical for regulatory
    documents where "bedrijfsfunctie" ≈ "business function" ≈ "capability"
    and a dense-only retrieval would miss the semantic connection.
    """

    def __init__(self, model: str = "mixedbread-ai/mxbai-rerank-large-v2"):
        self.model = model
        self._pipelines = None

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 20
    ) -> list[SearchResult]:
        if not results:
            return []

        try:
            from sentence_transformers import CrossEncoder

            if self._pipelines is None:
                self._pipelines = CrossEncoder(self.model)
            encoder = self._pipelines
        except ImportError:
            return results[:top_k]

        pairs = [(query, r.content) for r in results]
        scores = encoder.predict(pairs)

        scored = list(zip(scores, results))
        scored.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for score, result in scored[:top_k]:
            r = SearchResult(
                chunk_id=result.chunk_id,
                source_id=result.source_id,
                source_type=result.source_type,
                title=result.title,
                content=result.content,
                context_prefix=result.context_prefix,
                score=float(score),
                dense_score=result.dense_score,
                sparse_score=result.sparse_score,
                fts_score=result.fts_score,
                persona_relevance=result.persona_relevance,
                section=result.section,
                metadata=result.metadata,
            )
            reranked.append(r)

        return reranked


class IdentityReranker:
    """No-op reranker — returns results unchanged. Used when no model available."""

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 20
    ) -> list[SearchResult]:
        return results[:top_k]


class HyDEReranker:
    """Hypothetical Document Embeddings + cross-encoder reranking.

    Two-step retrieval improvement:
      1. Generate a hypothetical answer (HyDE) to the query using the LLM
      2. Embed the hypothetical answer alongside the original query
      3. Retrieve using both query and hypothetical embeddings
      4. Rerank results with cross-encoder

    HyDE helps because the hypothetical answer is closer in embedding space
    to relevant documents than the short query alone. For regulatory docs,
    "What NEN 7510 controls apply to access logging?" generates a hypothetical
    answer that CONTAINS "5.2 Toegangscontrole" — which embeds closer to the
    actual document chunk.
    """

    def __init__(self, reranker: Reranker | None = None, llm_client=None):
        self._reranker = reranker or IdentityReranker()
        self._llm = llm_client

    async def generate_hypothetical(
        self, query: str, persona_id: str = "", persona_focus: str = ""
    ) -> str:
        """Generate a hypothetical answer to use as an additional retrieval query."""
        if not self._llm:
            return query

        from preflight.llm.client import CallOpts

        persona_prefix = ""
        if persona_id and persona_focus:
            persona_prefix = f"from the perspective of {persona_id} ({persona_focus}), "

        prompt = (
            f"Write a brief, factual answer to this question {persona_prefix}"
            f"as if you found the exact passage in a Dutch hospital policy document.\n\n"
            f"Question: {query}\n\nAnswer (2-3 sentences, cite specific regulations if possible):"
        )

        try:
            response = await self._llm.call(
                system="You are a Dutch hospital policy expert. Answer precisely with regulatory references.",
                user=prompt,
                opts=CallOpts(temperature=0.1, max_tokens=150),
            )
            return response.text.strip() if response.text else query
        except Exception:
            return query

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 20
    ) -> list[SearchResult]:
        return await self._reranker.rerank(query, results, top_k)


def create_reranker(
    model: str = "mixedbread-ai/mxbai-rerank-large-v2",
    use_hyde: bool = False,
    llm_client=None,
) -> Reranker:
    """Factory: create the best available reranker.

    Tries MXBAI cross-encoder. Falls back to identity (no reranking).
    When use_hyde is True and llm_client is provided, wraps with HyDE
    so that generate_hypothetical() is available for per-persona queries.

    Note: use_hyde only takes effect here. When HyDEReranker is created
    directly (e.g. in CLI), this factory is not needed.
    """
    try:
        from sentence_transformers import CrossEncoder

        CrossEncoder(model)
        base: Reranker = MXBAIReranker(model)
    except (ImportError, OSError):
        base = IdentityReranker()

    if use_hyde and llm_client:
        return HyDEReranker(base, llm_client)

    return base
