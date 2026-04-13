"""Tests for preflight.embedding — client construction, router, hash."""

from preflight.embedding.client import (
    OllamaEmbedding,
    VoyageEmbedding,
    BGEMultilingualEmbedding,
    GeminiEmbedding,
    EmbeddingRouter,
    Vector,
    content_hash,
)


class TestVector:
    def test_dim_auto(self):
        v = Vector(dense=[1.0, 2.0, 3.0])
        assert v.dim == 3

    def test_empty(self):
        v = Vector(dense=[])
        assert v.dim == 0


class TestEmbeddingClients:
    def test_ollama_names(self):
        c = OllamaEmbedding("nomic-embed-text")
        assert c.model_name() == "nomic-embed-text"
        assert c.dimensions() == 768

    def test_voyage_names(self):
        c = VoyageEmbedding("voyage-3-large", dimensions=1024)
        assert c.model_name() == "voyage-3-large"
        assert c.dimensions() == 1024

    def test_bge_names(self):
        c = BGEMultilingualEmbedding()
        assert c.model_name() == "BAAI/bge-m3"

    def test_gemini_names(self):
        c = GeminiEmbedding()
        assert c.model_name() == "gemini-embedding-001"
        assert c.dimensions() == 768

    def test_gemini_custom_dims(self):
        c = GeminiEmbedding(dimensions=3072)
        assert c.dimensions() == 3072


class TestEmbeddingRouter:
    def test_from_ollama(self):
        r = EmbeddingRouter.from_ollama("nomic-embed-text")
        assert r._default.model_name() == "nomic-embed-text"

    def test_from_gemini(self):
        r = EmbeddingRouter.from_gemini()
        assert r._tabular.model_name() == "gemini-embedding-001"
        assert isinstance(r._tabular, GeminiEmbedding)

    def test_for_type_default(self):
        r = EmbeddingRouter.from_ollama()
        c = r.for_type("unknown")
        assert c.model_name() == r._default.model_name()

    def test_for_type_tabular(self):
        r = EmbeddingRouter.from_gemini()
        c = r.for_type("tabular")
        assert isinstance(c, GeminiEmbedding)

    def test_configure_override(self):
        r = EmbeddingRouter.from_ollama()
        gemini = GeminiEmbedding()
        r.configure(tabular=gemini)
        assert r._tabular is gemini


class TestContentHash:
    def test_deterministic(self):
        h1 = content_hash("test content")
        h2 = content_hash("test content")
        assert h1 == h2

    def test_different_content(self):
        h1 = content_hash("content a")
        h2 = content_hash("content b")
        assert h1 != h2
