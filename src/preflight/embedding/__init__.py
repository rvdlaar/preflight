"""
Preflight embedding module — client abstraction, chunking, contextual retrieval.

Architecture:
- EmbeddingClient protocol → pluggable backends (Ollama, Voyage, BGE, Gemini)
- ContextualRetriever → Anthropic-style context prepending before embedding
- Chunking → document-type-aware chunking (regulatory, technical, tabular)
- Hybrid vector support → dense + sparse in pgvector
"""

from preflight.embedding.client import (
    EmbeddingClient,
    EmbeddingRouter,
    EmbedOpts,
    EmbeddingResult,
    Vector,
    OllamaEmbedding,
    VoyageEmbedding,
    BGEMultilingualEmbedding,
    GeminiEmbedding,
    content_hash,
)
from preflight.embedding.parent_child import ParentSection, ChildChunk, parent_child_chunk

__all__ = [
    "EmbeddingClient",
    "EmbeddingRouter",
    "EmbedOpts",
    "EmbeddingResult",
    "Vector",
    "OllamaEmbedding",
    "VoyageEmbedding",
    "BGEMultilingualEmbedding",
    "GeminiEmbedding",
    "content_hash",
    "ParentSection",
    "ChildChunk",
    "parent_child_chunk",
]
