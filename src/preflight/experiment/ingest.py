"""
Preflight experiment ingestion — run PDF pipeline with current config.

Called by the runner. Uses config from experiment/config.py to control
all ingestion parameters. This is NOT the file the agent modifies.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from preflight.experiment.config import PipelineConfig

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PDF_DIR = PROJECT_ROOT

PDF_FILES = {
    "NEN-7510-1-2024": {
        "path": "NEN 7510-1_2024 nl.pdf",
        "content_type": "regulatory",
        "versie": "2024",
        "language": "nl",
    },
    "NEN-7510-2-2024": {
        "path": "NEN 7510-2_2024+A1_2026 nl.pdf",
        "content_type": "regulatory",
        "versie": "2024+A1:2026",
        "language": "nl",
    },
    "NEN-7512-2022": {
        "path": "NEN 7512_2022 nl.pdf",
        "content_type": "regulatory",
        "versie": "2022",
        "language": "nl",
    },
    "NEN-7513-2024": {
        "path": "NEN 7513_2024 nl.pdf",
        "content_type": "regulatory",
        "versie": "2024",
        "language": "nl",
    },
    "NTA-7516-2019": {
        "path": "NTA 7516_2019 nl.pdf",
        "content_type": "regulatory",
        "versie": "2019",
        "language": "nl",
    },
    "Novius-NAM": {
        "path": "Bedrijfsarchitectuur op basis van NAR - Hans Tonissen.pdf",
        "content_type": "policy",
        "versie": "2013",
        "language": "nl",
    },
}


async def ingest_all_pdfs(config: PipelineConfig) -> int:
    """Ingest all configured PDFs through the pipeline. Returns total chunks."""
    from preflight.parsing.parsers import ParsingPipeline
    from preflight.embedding.pipeline import ingest_document
    from preflight.embedding.client import EmbeddingRouter
    from preflight.embedding.contextual import StaticContextGenerator
    from preflight.retrieval.store import KnowledgeChunk, get_global_store, reset_global_store

    total_chunks = 0
    if config.embedding.router == "local":
        router = EmbeddingRouter.from_local(
            model=config.embedding.model,
            dimensions=config.embedding.dimensions,
        )
    else:
        router = EmbeddingRouter.from_ollama(
            model=config.embedding.model,
        )
    reset_global_store()
    store = get_global_store()

    pipeline = ParsingPipeline()

    for source_id, info in PDF_FILES.items():
        pdf_path = PDF_DIR / info["path"]
        if not pdf_path.exists():
            logger.warning("PDF not found: %s", pdf_path)
            continue

        logger.info("Ingesting %s (%s)", source_id, info["path"])

        try:
            parsed = await pipeline.parse(pdf_path)
        except Exception as e:
            logger.error("Failed to parse %s: %s", source_id, e)
            continue

        text = parsed.content
        if not text.strip():
            logger.warning("No text extracted from %s", source_id)
            continue

        versie = info["versie"]
        if parsed.metadata.get("versie") and parsed.metadata["versie"] != "unknown":
            versie = parsed.metadata["versie"]

        metadata = {
            "versie": versie,
            "source_id": source_id,
            "source_file": info["path"],
            "doc_title": parsed.title or source_id.replace("-", " "),
        }

        try:
            ingested = await ingest_document(
                text=text,
                content_type=info["content_type"],
                source_id=source_id,
                source_file=info["path"],
                title=parsed.title or source_id.replace("-", " "),
                language=info["language"],
                metadata=metadata,
                embedding_router=router,
                context_generator=StaticContextGenerator(),
                use_parent_child=True,
                child_chunk_size=config.chunking.child_chunk_size,
                child_overlap=config.chunking.child_overlap,
            )

            ctx_by_idx = {i: c for i, c in enumerate(ingested.contextualized)}
            parent_by_id = {p.id: p for p in getattr(ingested, "parent_sections", [])}

            chunks_for_store: list[KnowledgeChunk] = []
            for i, chunk in enumerate(ingested.chunks):
                vec = ingested.vectors[i] if i < len(ingested.vectors) else None
                dense = vec.dense if vec and vec.dense else []
                if not dense:
                    logger.warning("Skipping chunk %d of %s: no embedding vector", i, source_id)
                    continue
                ctx = ctx_by_idx.get(i)
                chunk_text = ctx.full_text if ctx else chunk.text
                ctx_prefix = ctx.context_prefix if ctx else ""

                pid = chunk.metadata.get("parent_id", "")
                pcontent = ""
                if pid and pid in parent_by_id:
                    pcontent = parent_by_id[pid].text[:2000]

                chunks_for_store.append(
                    KnowledgeChunk(
                        id=str(uuid.uuid4()),
                        source_id=source_id,
                        source_type=info["content_type"],
                        title=parsed.title or source_id.replace("-", " "),
                        content=chunk.text,
                        chunk_text=chunk_text,
                        dense_vector=dense,
                        language=info["language"],
                        section=chunk.metadata.get("section", ""),
                        content_type=info["content_type"],
                        context_prefix=ctx_prefix,
                        metadata=chunk.metadata,
                        parent_id=pid,
                        parent_content=pcontent,
                        chapter_num=chunk.metadata.get("chapter_num", 0),
                        chapter_title=chunk.metadata.get("chapter_title", ""),
                        versie=chunk.metadata.get("versie", versie),
                    )
                )

            if chunks_for_store:
                await store.upsert(chunks_for_store)

            total_chunks += len(ingested.chunks)
            logger.info(
                "Ingested %s: %d chunks, %d errors",
                source_id,
                len(ingested.chunks),
                len(ingested.errors),
            )
            if ingested.errors:
                for err in ingested.errors:
                    logger.warning("  Error: %s", err)
        except Exception as e:
            logger.error("Failed to ingest %s: %s", source_id, e)

    return total_chunks
