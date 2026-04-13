"""
Preflight CLI — Phase 0: One command, one assessment, one output.

Usage:
    preflight assess "we want Digital Pathology from Sysmex"
    preflight assess "we want Digital Pathology from Sysmex" --mode fast --model llama3.1:8b
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time

import click

from preflight.llm.client import CallOpts, LLMRouter
from preflight.llm.parser import (
    parse_deep_assessment,
    parse_fast_assessment,
)
from preflight.llm.prompt import (
    PERSPECTIVES,
    build_deep_assessment_prompt,
    build_fast_assessment_prompt,
)

# ---------------------------------------------------------------------------
# Core assessment logic
# ---------------------------------------------------------------------------


async def run_assessment(
    description: str,
    model: str = "llama3.1:8b",
    mode: str = "fast",
    ollama_url: str = "http://localhost:11434",
    perspectives: list[str] | None = None,
    landscape: str | None = None,
    context: dict[str, str] | None = None,
) -> dict:
    router = LLMRouter.from_ollama(model, ollama_url)

    if mode == "fast":
        return await _run_fast(router, description, perspectives, landscape, context)
    else:
        return await _run_deep(router, description, perspectives, landscape, context)


async def _run_fast(
    router: LLMRouter,
    description: str,
    perspective_ids: list[str] | None,
    landscape: str | None,
    context: dict[str, str] | None,
) -> dict:
    if not perspective_ids:
        perspective_ids = [p["id"] for p in PERSPECTIVES[:12]]

    system, user = build_fast_assessment_prompt(
        request_description=description,
        selected_perspective_ids=perspective_ids,
        landscape_context=landscape,
        retrieved_context=context,
    )

    click.echo(
        f"→ Calling LLM ({router.light().model_name()}) for batched assessment...",
        err=True,
    )
    start = time.perf_counter()

    response = await router.light().call(
        system=system, user=user, opts=CallOpts(temperature=0.3, max_tokens=4096)
    )

    elapsed = time.perf_counter() - start
    click.echo(f"→ Response received in {elapsed:.1f}s ({len(response.text)} chars)", err=True)

    parsed = parse_fast_assessment(response.text)

    click.echo(
        f"→ Parsed {len(parsed.ratings)} ratings (confidence: {parsed.parse_confidence:.0%})",
        err=True,
    )

    results = []
    for r in parsed.ratings:
        results.append(
            {
                "perspective_id": r.perspective_id,
                "rating": r.rating,
                "reason": r.reason,
                "conditions": r.conditions,
            }
        )

    output = {
        "mode": "fast",
        "model": router.light().model_name(),
        "description": description,
        "perspectives_used": perspective_ids,
        "ratings": results,
        "parse_confidence": parsed.parse_confidence,
        "unparsed": parsed.unparsed[:500] if parsed.unparsed else None,
        "usage": response.usage,
        "latency_ms": response.latency_ms,
    }

    if parsed.parse_confidence < 0.5:
        output["warning"] = (
            "Low parse confidence — raw LLM output may not follow expected format. Architect review required."
        )

    return output


async def _run_deep(
    router: LLMRouter,
    description: str,
    perspective_ids: list[str] | None,
    landscape: str | None,
    context: dict[str, str] | None,
) -> dict:
    if not perspective_ids:
        perspective_ids = [p["id"] for p in PERSPECTIVES[:8]]

    selected = [p for p in PERSPECTIVES if p["id"] in perspective_ids]
    results = []

    for persona in selected:
        persona_context = context.get(persona["id"], "") if context else None
        system, user = build_deep_assessment_prompt(
            persona=persona,
            request_description=description,
            landscape_context=landscape,
            retrieved_context=persona_context,
        )

        click.echo(f"→ Calling LLM for {persona['label']}...", err=True)
        start = time.perf_counter()

        client = router.strong()
        response = await client.call(
            system=system, user=user, opts=CallOpts(temperature=0.4, max_tokens=2048)
        )

        elapsed = time.perf_counter() - start
        parsed = parse_deep_assessment(response.text, persona["id"])

        click.echo(f"  {persona['label']}: {parsed.rating} ({elapsed:.1f}s)", err=True)

        results.append(
            {
                "perspective_id": persona["id"],
                "label": persona["label"],
                "role": persona["role"],
                "rating": parsed.rating,
                "findings": parsed.findings,
                "strongest_objection": parsed.strongest_objection,
                "hidden_concern": parsed.hidden_concern,
                "conditions": parsed.conditions,
                "rating_change_trigger": parsed.rating_change_trigger,
            }
        )

    return {
        "mode": "deep",
        "model": router.strong().model_name(),
        "description": description,
        "results": results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Preflight — EA intake and pre-assessment tool."""
    pass


@cli.command()
@click.argument("description")
@click.option(
    "--mode",
    type=click.Choice(["fast", "deep"]),
    default="fast",
    help="Assessment mode",
)
@click.option("--model", default="llama3.1:8b", help="Ollama model name")
@click.option("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
@click.option(
    "--perspectives",
    "-p",
    multiple=True,
    help="Perspective IDs to include (default: all)",
)
@click.option("--landscape", type=click.Path(exists=True), help="Path to landscape context file")
@click.option(
    "--context",
    type=click.Path(exists=True),
    help="Path to retrieved context JSON file",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "summary"]),
    default="summary",
    help="Output format",
)
def assess(
    description: str,
    mode: str,
    model: str,
    ollama_url: str,
    perspectives: tuple,
    landscape: str | None,
    context: str | None,
    output: str,
):
    """Assess a business request through the EA board personas.

    DEPRECATED: Use 'full-assess' for the complete pipeline (classification,
    triage floors, BIV, conditions, authority actions, documents).
    This command runs a direct LLM call without the full pipeline.
    """
    click.echo(
        "⚠  'assess' is deprecated. Use 'preflight full-assess' for the complete pipeline.",
        err=True,
    )
    landscape_text = None
    if landscape:
        with open(landscape, encoding="utf-8") as f:
            landscape_text = f.read()

    context_dict = None
    if context:
        with open(context, encoding="utf-8") as f:
            context_dict = json.load(f)

    perspective_list = list(perspectives) if perspectives else None

    result = asyncio.run(
        run_assessment(
            description=description,
            model=model,
            mode=mode,
            ollama_url=ollama_url,
            perspectives=perspective_list,
            landscape=landscape_text,
            context=context_dict,
        )
    )

    if output == "json":
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_summary(result)


def _print_summary(result: dict):
    click.echo()
    click.echo("=" * 80)
    click.echo(f"  PREFLIGHT ASSESSMENT — {result.get('description', '')[:60]}")
    click.echo(f"  Mode: {result.get('mode', '?')} | Model: {result.get('model', '?')}")
    click.echo("=" * 80)

    if result.get("mode") == "fast":
        _print_fast_summary(result)
    else:
        _print_deep_summary(result)

    if result.get("warning"):
        click.echo()
        click.echo(f"  ⚠  {result['warning']}")

    click.echo()
    click.echo("  This is a DRAFT assessment. The architect owns the final assessment.")
    click.echo("  The board owns the decision. Preflight provides analysis, not judgment.")
    click.echo("=" * 80)


def _print_fast_summary(result: dict):
    ratings = result.get("ratings", [])
    if not ratings:
        click.echo("  No ratings parsed from LLM output.")
        if result.get("unparsed"):
            click.echo(f"  Raw output (first 500 chars): {result['unparsed']}")
        return

    blocks = [r for r in ratings if r["rating"] == "block"]
    concerns = [r for r in ratings if r["rating"] == "concern"]
    conditionals = [r for r in ratings if r["rating"] == "conditional"]
    approves = [r for r in ratings if r["rating"] == "approve"]

    click.echo()
    click.echo(
        f"  Approve: {len(approves)}  |  Conditional: {len(conditionals)}  |  Concern: {len(concerns)}  |  Block: {len(blocks)}"
    )
    click.echo(f"  Parse confidence: {result.get('parse_confidence', 0):.0%}")
    click.echo()

    if blocks:
        click.echo("  ⛔ BLOCKS:")
        for r in blocks:
            click.echo(f"     {r['perspective_id']}: {r.get('reason', '(no reason parsed)')}")

    if concerns:
        click.echo("  ⚠️  CONCERNS:")
        for r in concerns:
            click.echo(f"     {r['perspective_id']}: {r.get('reason', '(no reason parsed)')}")

    if conditionals:
        click.echo("  📋 CONDITIONS:")
        for r in conditionals:
            conds = r.get("conditions", [])
            cond_text = "; ".join(conds) if conds else r.get("reason", "")
            click.echo(f"     {r['perspective_id']}: {cond_text}")


def _print_deep_summary(result: dict):
    for r in result.get("results", []):
        rating_icon = {
            "approve": "✅",
            "conditional": "📋",
            "concern": "⚠️",
            "block": "⛔",
        }.get(r["rating"], "?")
        click.echo()
        click.echo(f"  {rating_icon}  {r['label']} ({r['role']}) — {r['rating'].upper()}")
        for f in r.get("findings", []):
            click.echo(f"     • {f}")
        if r.get("strongest_objection"):
            click.echo(f"     Strongest objection: {r['strongest_objection']}")
        if r.get("conditions"):
            click.echo(f"     Conditions: {'; '.join(r['conditions'])}")


def main():
    cli()


# ---------------------------------------------------------------------------
# Full pipeline command (Steps 0-5: classify → select → assess → challenge → output)
# ---------------------------------------------------------------------------


@cli.command("full-assess")
@click.argument("description")
@click.option(
    "--mode",
    type=click.Choice(["fast", "deep"]),
    default="fast",
    help="Assessment mode",
)
@click.option("--model", default="llama3.1:8b", help="Ollama model name")
@click.option("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
@click.option(
    "--heuristic-classify",
    is_flag=True,
    help="Use heuristic classification instead of LLM",
)
@click.option(
    "--dual-classify",
    type=click.Choice(["auto", "always", "off"]),
    default="auto",
    help="Dual classification: auto=for high/critical, always=always, off=never",
)
@click.option(
    "--archimate",
    type=click.Path(exists=True),
    help="Path to .archimate XML file for landscape context",
)
@click.option("--store-url", default=None, help="PostgreSQL URL for pgvector retrieval")
@click.option(
    "--embed-model",
    default="nomic-embed-text",
    help="Ollama embedding model for retrieval",
)
@click.option(
    "--reranker/--no-reranker",
    default=False,
    help="Enable cross-encoder reranking of retrieved results",
)
@click.option(
    "--hyde/--no-hyde",
    default=False,
    help="Enable HyDE (Hypothetical Document Embeddings) for query expansion",
)
@click.option(
    "--language",
    type=click.Choice(["nl", "en"]),
    default="nl",
    help="Output language (nl=Dutch, en=English)",
)
@click.option(
    "--interaction-rounds",
    type=int,
    default=2,
    help="Number of interaction rounds in deep mode (default: 2)",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "summary"]),
    default="summary",
    help="Output format",
)
def full_assess(
    description: str,
    mode: str,
    model: str,
    ollama_url: str,
    heuristic_classify: bool,
    dual_classify: str,
    archimate: str | None,
    store_url: str | None,
    embed_model: str,
    reranker: bool,
    hyde: bool,
    language: str,
    interaction_rounds: int,
    output: str,
):
    """Full pipeline: classify → select perspectives → assess → synthesize output."""
    from preflight.archimate import build_landscape_context, parse_archimate
    from preflight.pipeline.orchestrator import run_full_pipeline

    router = LLMRouter.from_ollama(model, ollama_url)

    landscape_context = None
    if archimate:
        archi_model = parse_archimate(archimate)
        keywords = description.lower().split()[:10]
        landscape_context = build_landscape_context(archi_model, keywords)
        click.echo(
            f"→ Landscape: {len(landscape_context.get('existingApps', []))} existing apps found",
            err=True,
        )

    embedding_router = None
    vector_store = None
    reranker_instance = None

    if store_url:
        from preflight.embedding.client import EmbeddingRouter as EmbRouter
        from preflight.retrieval.store import PgvectorStore

        embedding_router = EmbRouter.from_ollama(embed_model, ollama_url)
        vector_store = PgvectorStore(store_url)
        click.echo(f"→ Vector store configured (model: {embed_model})", err=True)

        if reranker:
            from preflight.retrieval.reranker import create_reranker

            reranker_instance = create_reranker("mxbai")
            click.echo("→ Cross-encoder reranker enabled", err=True)

        if hyde:
            from preflight.retrieval.reranker import HyDEReranker

            reranker_instance = HyDEReranker(
                reranker=reranker_instance,
                llm_client=router.light(),
            )
            click.echo("→ HyDE query expansion enabled", err=True)

    dual_flag = None
    if dual_classify == "always":
        dual_flag = True
    elif dual_classify == "off":
        dual_flag = False
    # "auto" → None, orchestrator handles per-impact-level

    click.echo("→ Classifying request...", err=True)

    result = asyncio.run(
        run_full_pipeline(
            request=description,
            client=router,
            landscape_context=landscape_context,
            mode=mode,
            prefer_heuristic_classify=heuristic_classify,
            dual_classify=dual_flag,
            embedding_router=embedding_router,
            vector_store=vector_store,
            reranker=reranker_instance,
            use_hyde=hyde,
            language=language,
            interaction_rounds=interaction_rounds,
        )
    )

    if result.errors:
        for err in result.errors:
            click.echo(f"⚠  {err}", err=True)

    if output == "json":
        import dataclasses

        result_dict = dataclasses.asdict(result)
        click.echo(json.dumps(result_dict, indent=2, ensure_ascii=False, default=str))
    else:
        _print_full_summary(result)


def _print_full_summary(result):
    cls = result.classification
    if cls:
        click.echo()
        click.echo("=" * 80)
        click.echo(f"  PREFLIGHT ASSESSMENT — {cls.summary_en or '<request>'}")
        click.echo(
            f"  Type: {cls.request_type} | Impact: {cls.impact_level} | Confidence: {cls.confidence:.0%}"
        )
        click.echo(f"  Method: {cls.method} | Triage: {result.triage.get('treatment', '?')}")
        if cls.dual:
            div = cls.divergence or "agreement"
            click.echo(f"  Dual Classification: {div}")
        click.echo("=" * 80)

    if result.perspectives:
        click.echo(
            f"\n  Perspectives ({len(result.perspectives)}): {', '.join(result.perspectives)}"
        )

    if result.biv:
        click.echo(
            f"  BIV: B={result.biv.get('B', '?')} I={result.biv.get('I', '?')} V={result.biv.get('V', '?')}"
        )

    if result.authority_actions:
        click.echo("\n  Authority Actions:")
        for action in result.authority_actions:
            click.echo(
                f"    {action.get('type', '?')}: {action.get('persona', '?')} - {action.get('finding', '')[:80]}"
            )

    if result.persona_findings:
        click.echo("\n  Persona Findings:")
        for pf in result.persona_findings:
            pid = pf.get("perspective_id", "?")
            rating = pf.get("rating", "?")
            click.echo(f"    {pid}: {rating}")

    if result.documents:
        click.echo(f"\n  Documents generated: {', '.join(result.documents.keys())}")

    if result.diagrams:
        click.echo(f"  Diagrams generated: {', '.join(result.diagrams.keys())}")

    click.echo()
    click.echo("  This is a DRAFT assessment. The architect owns the final assessment.")
    click.echo("=" * 80)


@cli.command("ingest")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--content-type",
    type=click.Choice(["regulatory", "vendor", "policy", "archimate", "tabular", "generic"]),
    default=None,
    help="Override content type detection",
)
@click.option("--source-id", default=None, help="Override source ID (default: filename)")
@click.option("--language", type=click.Choice(["nl", "en", "mixed"]), default="nl")
@click.option(
    "--parse-mode",
    type=click.Choice(["workhorse", "smart"]),
    default="workhorse",
    help="Parsing mode (smart requires LlamaParse API key)",
)
@click.option("--no-embed", is_flag=True, help="Skip embedding (parse + chunk only)")
@click.option("--embed-model", default="nomic-embed-text", help="Ollama embedding model")
@click.option("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
@click.option("--store-url", default=None, help="PostgreSQL URL for pgvector store")
@click.option(
    "--contextual/--no-contextual",
    default=True,
    help="Add contextual prefixes (Anthropic-style contextual retrieval)",
)
@click.option(
    "--context-llm",
    type=click.Choice(["static", "ollama"]),
    default="static",
    help="Context generation mode (static=metadata only, ollama=LLM-generated)",
)
@click.option("--context-model", default="llama3.1:8b", help="Ollama model for context generation")
@click.option(
    "--persona-tag",
    "-t",
    multiple=True,
    help="Tag with persona relevance (e.g., -t security -t risk)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be ingested without storing")
def ingest(
    path: str,
    content_type: str | None,
    source_id: str | None,
    language: str,
    parse_mode: str,
    no_embed: bool,
    embed_model: str,
    ollama_url: str,
    store_url: str | None,
    contextual: bool,
    context_llm: str,
    context_model: str,
    persona_tag: tuple,
    dry_run: bool,
):
    """Ingest a document into the knowledge base.

    Parses the document, chunks it, adds contextual prefixes, and stores
    in the vector database for per-persona RAG retrieval.

    Supports: PDF, DOCX, PPTX, XLSX, MD, TXT, .archimate XML
    """
    from pathlib import Path as P

    from preflight.embedding.client import EmbeddingRouter
    from preflight.embedding.contextual import (
        LLMContextGenerator,
        StaticContextGenerator,
    )
    from preflight.embedding.pipeline import ingest_document
    from preflight.llm.client import OllamaClient
    from preflight.parsing.parsers import ParseMode, ParsingPipeline

    file_path = P(path)
    sid = source_id or file_path.stem
    ext = file_path.suffix.lower()

    pm = ParseMode.SMART if parse_mode == "smart" else ParseMode.WORKHORSE
    parsing_pipeline = ParsingPipeline(mode=pm)

    async def _run_ingest():
        nonlocal parsed, doc, store

        click.echo(f"→ Parsing {file_path.name}...", err=True)
        parsed_data = await parsing_pipeline.parse(file_path)

        if not parsed_data.quality_ok:
            click.echo(f"⚠ Parse issues: {'; '.join(parsed_data.errors)}", err=True)
            if not parsed_data.content:
                click.echo("✗ No content extracted. Aborting.", err=True)
                sys.exit(1)

        for w in parsed_data.warnings:
            click.echo(f"⚠ {w}", err=True)

        click.echo(
            f"→ Parsed: {len(parsed_data.content)} chars, "
            f"{parsed_data.page_count} pages, "
            f"language={parsed_data.language}, "
            f"type={parsed_data.content_type}",
            err=True,
        )

        ctype = content_type or parsed_data.content_type
        meta = {
            "doc_title": parsed_data.title or file_path.stem,
            "language": language or parsed_data.language,
            "source_id": sid,
        }
        if parsed_data.metadata.get("versie"):
            meta["versie"] = parsed_data.metadata["versie"]
        if persona_tag:
            meta["domains"] = ",".join(persona_tag)

        embedding_router = None
        if not no_embed and not dry_run:
            embedding_router = EmbeddingRouter.from_ollama(embed_model, ollama_url)

        context_generator = None
        if contextual:
            if context_llm == "ollama":
                llm_client = OllamaClient(context_model, ollama_url)
                context_generator = LLMContextGenerator(llm_client)
            else:
                context_generator = StaticContextGenerator()

        if ext == ".archimate":
            from preflight.archimate.parser import parse_archimate

            model = parse_archimate(str(file_path))
            elements = [
                {
                    "id": e.id,
                    "type": e.type,
                    "name": e.name,
                    "layer": getattr(e, "layer", "Application"),
                    "properties": e.properties,
                }
                for e in model.elements
            ]
            relationships = [
                {
                    "source_id": r.source,
                    "target_id": r.target,
                    "relationship_type": r.type,
                    "source_name": "",
                    "target_name": "",
                }
                for r in model.relationships
            ]

            doc = await ingest_document(
                text="",
                content_type="archimate",
                source_id=sid,
                source_file=str(file_path),
                title=parsed_data.title or "ArchiMate Model",
                language=language,
                metadata={**meta},
                embedding_router=embedding_router,
                context_generator=context_generator,
                archimate_elements=elements,
                archimate_relationships=relationships,
            )
        else:
            doc = await ingest_document(
                text=parsed_data.content,
                content_type=ctype,
                source_id=sid,
                source_file=str(file_path),
                title=parsed_data.title,
                language=language,
                metadata={**meta},
                embedding_router=embedding_router,
                context_generator=context_generator,
            )

        if doc.errors:
            for e in doc.errors:
                click.echo(f"⚠ {e}", err=True)

        if dry_run:
            click.echo("\n--- DRY RUN ---")
            click.echo(f"Source:     {doc.source_id}")
            click.echo(f"Type:       {doc.content_type}")
            click.echo(f"Chunks:     {len(doc.chunks)}")
            click.echo(f"Vectors:    {len(doc.vectors)}")
            if doc.chunks:
                click.echo("\nFirst chunk preview:")
                click.echo(doc.chunks[0].text[:300])
            if doc.contextualized:
                click.echo("\nContextualized first chunk:")
                click.echo(doc.contextualized[0].full_text[:400])
            return

        if store_url:
            from preflight.retrieval.enrichment import enrich_chunk
            from preflight.retrieval.store import KnowledgeChunk, PgvectorStore

            store = PgvectorStore(store_url)
            await store.ensure_schema()

            chunks_to_store: list[KnowledgeChunk] = []
            for i, chunk in enumerate(doc.chunks):
                ctx = doc.contextualized[i] if i < len(doc.contextualized) else None
                vec = doc.vectors[i] if i < len(doc.vectors) else None

                persona_rel = list(persona_tag) if persona_tag else []
                if chunk.metadata.get("domains"):
                    persona_rel = [
                        d.strip() for d in chunk.metadata["domains"].split(",") if d.strip()
                    ]

                source_type = doc.content_type
                chunk_text = ctx.full_text if ctx else chunk.text

                enriched = enrich_chunk(
                    content=chunk_text,
                    title=doc.title,
                    doc_summary=doc.title,
                    chunk_context=ctx.context_prefix if ctx else "",
                    source_type=source_type,
                    persona_tags=persona_rel,
                    language=doc.language,
                )

                title_vec = None
                if vec and vec.dense and embedding_router:
                    try:
                        title_vec_result = await embedding_router.embed_query_for_type(
                            doc.title, source_type
                        )
                        title_vec = title_vec_result.dense
                    except Exception as e:
                        logging.getLogger(__name__).warning(
                            f"Title embedding failed for '{doc.title}': {e}"
                        )
                        title_vec = None

                chunks_to_store.append(
                    KnowledgeChunk(
                        id="",
                        source_id=doc.source_id,
                        source_type=source_type,
                        title=doc.title,
                        content=chunk.text,
                        chunk_text=chunk_text,
                        dense_vector=vec.dense if vec and vec.dense else [],
                        title_vector=title_vec,
                        language=doc.language,
                        section=chunk.metadata.get("section", ""),
                        page_number=chunk.metadata.get("page_number"),
                        persona_relevance=persona_rel,
                        content_type=doc.content_type,
                        classification=meta.get("classification", "internal"),
                        context_prefix=ctx.context_prefix if ctx else "",
                        enriched_keyword=enriched.keyword_enriched,
                        enriched_semantic=enriched.semantic_enriched,
                        metadata={**chunk.metadata},
                        parent_id=chunk.metadata.get("parent_id", ""),
                        parent_content=chunk.metadata.get("parent_content", ""),
                        chapter_num=chunk.metadata.get("chapter_num", 0),
                        chapter_title=chunk.metadata.get("chapter_title", ""),
                        versie=chunk.metadata.get("versie", meta.get("versie", "")),
                    )
                )

            ids = await store.upsert(chunks_to_store)
            click.echo(f"→ Stored {len(ids)} chunks in pgvector", err=True)

            stats = await store.get_stats()
            click.echo(
                f"→ Knowledge base: {stats['total_chunks']} chunks, "
                f"{stats['total_sources']} sources",
                err=True,
            )
        else:
            click.echo(
                f"→ Ingested: {len(doc.chunks)} chunks, {len(doc.vectors)} vectors",
                err=True,
            )
            click.echo("  (No --store-url provided; results not persisted)", err=True)

        click.echo(f"✓ Ingest complete for {doc.source_id}")

    parsed = None
    doc = None
    store = None
    asyncio.run(_run_ingest())


@cli.command("quick-scan")
@click.argument("description")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "summary"]),
    default="summary",
    help="Output format",
)
def quick_scan(description: str, output: str):
    """Quick 30-second check: classify + triage floors + red-flag detection.

    No LLM calls for assessment — only heuristic classification plus
    triage floor rules. Tells you whether to proceed, proceed with
    caution, or stop and run a full assessment.
    """
    from preflight.pipeline.quickscan import quick_scan as qs

    result = qs(description)

    if output == "json":
        import dataclasses

        click.echo(
            json.dumps(dataclasses.asdict(result), indent=2, ensure_ascii=False, default=str)
        )
        return

    click.echo()
    click.echo("=" * 80)
    click.echo(f"  QUICK SCAN — {description[:60]}")
    click.echo("=" * 80)

    cls = result.classification
    click.echo(
        f"  Type: {cls.request_type} | Impact: {cls.impact_level} | Confidence: {cls.confidence:.0%}"
    )
    click.echo(f"  Triage: {result.triage.get('treatment', '?')}")
    click.echo(
        f"  Perspectives: {', '.join(result.perspectives[:8])}{'...' if len(result.perspectives) > 8 else ''}"
    )

    verdict_icons = {
        "PROCEED": "✅",
        "PROCEED_WITH_CAUTION": "⚠️",
        "STOP_AND_ASSESS": "⛔",
    }
    icon = verdict_icons.get(result.verdict.value, "?")
    click.echo()
    click.echo(f"  {icon}  VERDICT: {result.verdict.value}")

    if result.red_flags:
        click.echo()
        click.echo("  RED FLAGS:")
        for rf in result.red_flags:
            click.echo(f"    ⛔ {rf}")

    if result.warnings:
        click.echo()
        click.echo("  WARNINGS:")
        for w in result.warnings:
            click.echo(f"    ⚠️  {w}")

    click.echo()
    click.echo(f"  Recommendation: {result.recommendation}")
    click.echo(f"  Estimated assessment time: {result.estimated_assessment_time}")
    click.echo()
    click.echo("  This is a heuristic quick scan. Run 'full-assess' for LLM-driven analysis.")
    click.echo("=" * 80)


if __name__ == "__main__":
    main()
