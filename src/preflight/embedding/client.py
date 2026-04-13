"""
Preflight embedding client abstraction.

Mirrors the LLM router pattern: Protocol-based, async-first, tiered routing.
Phase 1 uses a single model for all tiers. Split when you have data.

Design decisions:
- Protocol, not inheritance — duck typing
- Async — embedding is I/O bound
- Batch support — embed per-persona context bundles in one call
- Dense + sparse vectors — pgvector supports both (v0.8+)
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass
class Vector:
    dense: list[float]
    sparse: dict[int, float] | None = None
    dim: int = 0

    def __post_init__(self):
        self.dim = len(self.dense) if self.dense else 0


@dataclass
class EmbeddingResult:
    vectors: list[Vector]
    model: str
    latency_ms: float = 0.0
    token_count: int = 0


@dataclass
class EmbedOpts:
    batch_size: int = 64
    include_sparse: bool = False
    model_override: str | None = None


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str], opts: EmbedOpts | None = None) -> EmbeddingResult: ...

    async def embed_query(self, text: str) -> Vector: ...

    def model_name(self) -> str: ...

    def dimensions(self) -> int: ...


class OllamaEmbedding:
    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        dimensions: int = 768,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dimensions = dimensions

    def model_name(self) -> str:
        return self.model

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], opts: EmbedOpts | None = None) -> EmbeddingResult:
        import asyncio
        import httpx

        opts = opts or EmbedOpts()
        start = time.perf_counter()
        vectors: list[Vector] = []
        total_tokens = 0

        for text in texts:
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        resp = await client.post(
                            f"{self.base_url}/api/embeddings",
                            json={"model": self.model, "prompt": text},
                        )
                        if resp.status_code in (500, 503):
                            await asyncio.sleep(0.3 * (attempt + 1))
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                except Exception as e:
                    if attempt == 2:
                        vectors.append(Vector(dense=[]))
                        break
                    await asyncio.sleep(0.3 * (attempt + 1))
                    continue

                if isinstance(data, dict) and "embedding" in data:
                    vectors.append(Vector(dense=data["embedding"]))
                elif isinstance(data, dict) and "embeddings" in data:
                    vectors.append(
                        Vector(dense=data["embeddings"][0] if data["embeddings"] else [])
                    )
                else:
                    vectors.append(
                        Vector(
                            dense=data[0]["embedding"] if isinstance(data, list) and data else []
                        )
                    )
                total_tokens += data.get("prompt_eval_count", 0) or len(text.split()) * 4
                break

        latency_ms = (time.perf_counter() - start) * 1000
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            latency_ms=latency_ms,
            token_count=total_tokens,
        )

    async def embed_query(self, text: str) -> Vector:
        result = await self.embed([text])
        return result.vectors[0]


class VoyageEmbedding:
    def __init__(
        self,
        model: str = "voyage-3-large",
        api_key: str | None = None,
        base_url: str = "https://api.voyageai.com/v1",
        dimensions: int = 1024,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._dimensions = dimensions

    def model_name(self) -> str:
        return self.model

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], opts: EmbedOpts | None = None) -> EmbeddingResult:
        import httpx
        import os

        opts = opts or EmbedOpts()
        api_key = self.api_key or os.environ.get("VOYAGE_API_KEY", "")
        start = time.perf_counter()
        vectors: list[Vector] = []
        total_tokens = 0

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        for i in range(0, len(texts), opts.batch_size):
            batch = texts[i : i + opts.batch_size]
            payload = {
                "model": self.model,
                "input": batch,
                "input_type": "document",
            }
            if self._dimensions:
                payload["output_dimension"] = self._dimensions

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/embeddings", json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()

            for emb in data.get("data", []):
                vectors.append(Vector(dense=emb["embedding"]))

            total_tokens += data.get("usage", {}).get("total_tokens", 0)

        latency_ms = (time.perf_counter() - start) * 1000
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            latency_ms=latency_ms,
            token_count=total_tokens,
        )

    async def embed_query(self, text: str) -> Vector:
        import httpx
        import os

        api_key = self.api_key or os.environ.get("VOYAGE_API_KEY", "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": self.model,
            "input": [text],
            "input_type": "query",
        }
        if self._dimensions:
            payload["output_dimension"] = self._dimensions

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/embeddings", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return Vector(dense=data["data"][0]["embedding"])


class BGEMultilingualEmbedding:
    def __init__(
        self,
        model: str = "BAAI/bge-m3",
        base_url: str = "http://localhost:8080",
        dimensions: int = 1024,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dimensions = dimensions

    def model_name(self) -> str:
        return self.model

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], opts: EmbedOpts | None = None) -> EmbeddingResult:
        import httpx

        opts = opts or EmbedOpts()
        start = time.perf_counter()
        vectors: list[Vector] = []

        payload = {
            "model": self.model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/v1/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()

        for emb in data.get("data", []):
            vectors.append(Vector(dense=emb["embedding"]))

        latency_ms = (time.perf_counter() - start) * 1000
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            latency_ms=latency_ms,
        )

    async def embed_query(self, text: str) -> Vector:
        result = await self.embed([text])
        return result.vectors[0]


class GeminiEmbedding:
    def __init__(
        self,
        model: str = "gemini-embedding-001",
        dimensions: int = 768,
    ):
        self.model = model
        self._dimensions = dimensions

    def model_name(self) -> str:
        return self.model

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], opts: EmbedOpts | None = None) -> EmbeddingResult:
        import httpx
        import os

        opts = opts or EmbedOpts()
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        base_url = "https://generativelanguage.googleapis.com/v1beta"
        start = time.perf_counter()
        vectors: list[Vector] = []
        total_tokens = 0

        for i in range(0, len(texts), opts.batch_size):
            batch = texts[i : i + opts.batch_size]
            payload = {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": t} for t in batch]},
            }
            if self._dimensions:
                payload["outputDimensionality"] = self._dimensions

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base_url}/models/{self.model}:batchEmbedContents?key={api_key}",
                    json={
                        "requests": [
                            {
                                "model": f"models/{self.model}",
                                "content": {"parts": [{"text": t}]},
                                **(
                                    {"outputDimensionality": self._dimensions}
                                    if self._dimensions
                                    else {}
                                ),
                            }
                            for t in batch
                        ]
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            for emb in data.get("embeddings", []):
                vectors.append(Vector(dense=emb.get("values", [])))

            total_tokens += len(batch) * 4

        latency_ms = (time.perf_counter() - start) * 1000
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            latency_ms=latency_ms,
            token_count=total_tokens,
        )

    async def embed_query(self, text: str) -> Vector:
        result = await self.embed([text])
        return result.vectors[0]


class SentenceTransformerEmbedding:
    """Local embedding using sentence-transformers — no server needed.

    Downloads model weights on first use via HuggingFace, caches locally.
    Multilingual models (intfloat/multilingual-e5-small, BAAI/bge-m3)
    handle Dutch regulatory text much better than English-first models.
    One pip install covers everything — ideal for hospital IT with no ML ops.
    """

    def __init__(
        self,
        model: str = "intfloat/multilingual-e5-small",
        dimensions: int = 384,
    ):
        self.model_name = model
        self._dimensions = dimensions
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            actual_dim = self._model.get_sentence_embedding_dimension()
            if self._dimensions == 0:
                self._dimensions = actual_dim

    def model_name(self) -> str:
        return self.model_name

    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], opts: EmbedOpts | None = None) -> EmbeddingResult:
        import asyncio

        opts = opts or EmbedOpts()
        start = time.perf_counter()
        self._load()

        batch_size = min(opts.batch_size, 64)
        all_vectors: list[Vector] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            emb = self._model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
            for row in emb:
                vec = row.tolist() if hasattr(row, "tolist") else list(row)
                all_vectors.append(Vector(dense=vec))

        latency_ms = (time.perf_counter() - start) * 1000
        return EmbeddingResult(
            vectors=all_vectors,
            model=self.model_name,
            latency_ms=latency_ms,
            token_count=sum(len(t.split()) * 4 for t in texts),
        )

    async def embed_query(self, text: str) -> Vector:
        result = await self.embed([text])
        return result.vectors[0]


class EmbeddingRouter:
    """Route embedding calls by data type — different models for different content.

    Mirrors the LLM router pattern. Phase 1 uses a single model for all types.
    Split when retrieval quality data justifies it.

    Mapping (from ARCHITECTURE.md):
      ArchiMate objects  → Voyage-3-Large (preserves graph structure)
      Regulatory/specs  → Voyage-3-Large (dense regulatory text, contextual enrichment)
      Vendor docs (PDF) → BGE-M3 (multilingual NL/EN/DE)
      Tables/excel      → BGE-M3 (row-wise markdown)
      Queries           → same model as the document type they're targeting
    """

    def __init__(self, client: EmbeddingClient):
        self._default = client
        self._archimate = client
        self._regulatory = client
        self._vendor = client
        self._tabular = client

    def for_type(self, content_type: str) -> EmbeddingClient:
        mapping = {
            "archimate": self._archimate,
            "regulatory": self._regulatory,
            "vendor": self._vendor,
            "tabular": self._tabular,
        }
        return mapping.get(content_type, self._default)

    async def embed_for_type(
        self, texts: list[str], content_type: str, opts: EmbedOpts | None = None
    ) -> EmbeddingResult:
        client = self.for_type(content_type)
        return await client.embed(texts, opts)

    async def embed_query_for_type(self, text: str, content_type: str) -> Vector:
        client = self.for_type(content_type)
        return await client.embed_query(text)

    async def embed_query(self, text: str, content_type: str = "generic") -> Vector:
        return await self.embed_query_for_type(text, content_type)

    def configure(
        self,
        default: EmbeddingClient | None = None,
        archimate: EmbeddingClient | None = None,
        regulatory: EmbeddingClient | None = None,
        vendor: EmbeddingClient | None = None,
        tabular: EmbeddingClient | None = None,
    ):
        if default:
            self._default = default
        if archimate:
            self._archimate = archimate
        if regulatory:
            self._regulatory = regulatory
        if vendor:
            self._vendor = vendor
        if tabular:
            self._tabular = tabular

    @classmethod
    def from_local(
        cls,
        model: str = "intfloat/multilingual-e5-small",
        dimensions: int = 384,
    ) -> EmbeddingRouter:
        client = SentenceTransformerEmbedding(model, dimensions)
        return cls(client)

    @classmethod
    def from_ollama(
        cls, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"
    ) -> EmbeddingRouter:
        client = OllamaEmbedding(model, base_url)
        return cls(client)

    @classmethod
    def from_voyage(
        cls, api_key: str | None = None, model: str = "voyage-3-large"
    ) -> EmbeddingRouter:
        client = VoyageEmbedding(model, api_key)
        return cls(client)

    @classmethod
    def from_gemini(
        cls, model: str = "gemini-embedding-001", dimensions: int = 768
    ) -> EmbeddingRouter:
        gemini = GeminiEmbedding(model, dimensions)
        router = cls(gemini)
        router._tabular = gemini
        return router


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
