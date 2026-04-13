"""
Preflight per-persona retrieval — the core RAG pipeline.

Each of the 22 MiroFish personas has its own domain keywords, which scope
retrieval queries to relevant knowledge bundles. This is NOT global retrieval —
the Security persona retrieves security policies, the CMIO retrieves clinical
system documents, etc.

Pipeline:
  1. Expand persona domain keywords into augmented queries
  2. Embed augmented queries per content type
  3. Retrieve from vector store with persona filters
  4. Merge and deduplicate across sources
  5. Re-rank by cross-encoder (Phase 2+: mxbai-rerank)
  6. Build persona context bundles for the assessment prompt

This module connects the retrieval layer to the assessment pipeline
(orchestrator.py calls this in Step 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import re

from preflight.embedding.client import EmbeddingRouter
from preflight.retrieval.store import VectorStoreClient, SearchResult
from preflight.retrieval.reranker import (
    Reranker,
    IdentityReranker,
    HyDEReranker,
    create_reranker,
)
from preflight.retrieval.classify import classify_query, QueryIntent

_ENRICHMENT_LINE_PATTERN = re.compile(
    r"^[ \t]*(?:METADATA_KEYWORD|METADATA_SEMANTIC|ZIRA|REGS|DOMAIN|TYPE|SAMENVATTING|CONTEXT|TITLE|"
    r"ZiRA principle|Regulation|Relevant domains|Document type):.*$",
    re.MULTILINE | re.IGNORECASE,
)


def _cleanup_enrichment(text: str) -> str:
    """Strip enrichment metadata prefixes from retrieved content.

    Removes entire lines that start with enrichment markers (ZIRA:, REGS:,
    METADATA_KEYWORD:, etc.). These markers are always line-level in the
    enrichment format — inline occurrences don't happen in practice.
    """
    if not text:
        return text
    result = _ENRICHMENT_LINE_PATTERN.sub("", text)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip()


PERSONA_DOMAINS: dict[str, dict] = {
    "cio": {
        "keywords": [
            "IT strategy",
            "budget",
            "TCO",
            "shadow-IT",
            "roadmap",
            "investment",
        ],
        "source_types": ["policy", "standard"],
        "content_types": ["regulatory", "policy"],
    },
    "cmio": {
        "keywords": [
            "clinical",
            "patient safety",
            "HL7",
            "FHIR",
            "DICOM",
            "medical device",
            "MDR",
            "IVDR",
            "Cloverleaf",
            "JiveX",
            "Digizorg",
            "bedrijfsfunctie klinisch",
        ],
        "source_types": ["policy", "regulation", "archimate"],
        "content_types": ["regulatory", "archimate", "policy"],
    },
    "chief": {
        "keywords": [
            "ZiRA",
            "target architecture",
            "architecture principle",
            "capability",
            "bedrijfsfunctie",
            "dienstenmodel",
            "architecture debt",
        ],
        "source_types": ["standard", "archimate", "policy"],
        "content_types": ["regulatory", "archimate", "policy"],
    },
    "business": {
        "keywords": [
            "strategy",
            "business value",
            "stakeholder",
            "bedrijfsfunctie",
            "business case",
            "capability map",
        ],
        "source_types": ["policy", "strategy"],
        "content_types": ["regulatory", "policy"],
    },
    "process": {
        "keywords": [
            "care process",
            "workflow",
            "handover",
            "Wegiz",
            "procesmodel",
            "zorgproces",
            "verwijzing",
        ],
        "source_types": ["regulation", "policy"],
        "content_types": ["regulatory", "policy"],
    },
    "application": {
        "keywords": [
            "application portfolio",
            "tech radar",
            "SaaS",
            "vendor viability",
            "lifecycle",
            "applicatie",
            "portfolio overlap",
        ],
        "source_types": ["policy", "vendor", "archimate"],
        "content_types": ["vendor", "archimate", "policy"],
    },
    "integration": {
        "keywords": [
            "API",
            "integration",
            "Cloverleaf",
            "HL7",
            "FHIR",
            "data flow",
            "coupling risk",
            "interface",
            "interoperabiliteit",
        ],
        "source_types": ["policy", "standard", "archimate"],
        "content_types": ["archimate", "regulatory", "policy"],
    },
    "infrastructure": {
        "keywords": [
            "hosting",
            "DR",
            "RPO",
            "RTO",
            "capacity",
            "monitoring",
            "infrastructure",
            "network",
            "virtualisatie",
        ],
        "source_types": ["policy", "archimate"],
        "content_types": ["policy", "archimate"],
    },
    "data": {
        "keywords": [
            "data classification",
            "GDPR",
            "AVG",
            "DPIA",
            "EU AI Act",
            "verwerkingsregister",
            "privacy",
            "persoonsgegevens",
        ],
        "source_types": ["regulation", "policy"],
        "content_types": ["regulatory", "policy"],
    },
    "security": {
        "keywords": [
            "STRIDE",
            "zero trust",
            "IAM",
            "encryption",
            "NEN 7510",
            "NEN 7512",
            "SBOM",
            "vulnerability",
            "penetration test",
            "security architecture",
        ],
        "source_types": ["regulation", "standard", "policy"],
        "content_types": ["regulatory", "policy"],
    },
    "ciso": {
        "keywords": [
            "security risk",
            "SOC",
            "incident response",
            "security governance",
            "beveiligingsbeleid",
            "incidentmanagement",
        ],
        "source_types": ["policy", "regulation"],
        "content_types": ["regulatory", "policy"],
    },
    "iso-officer": {
        "keywords": [
            "NEN 7510",
            "ISMS",
            "patch cycle",
            "vulnerability management",
            "compliance monitoring",
            "informatiebeveiliging",
        ],
        "source_types": ["regulation", "standard"],
        "content_types": ["regulatory", "policy"],
    },
    "risk": {
        "keywords": [
            "NEN 7510",
            "NEN 7512",
            "NEN 7513",
            "NIS2",
            "AIVG 2022",
            "vendor compliance",
            "verwerkersovereenkomst",
            "risk assessment",
        ],
        "source_types": ["regulation", "standard", "policy"],
        "content_types": ["regulatory", "policy"],
    },
    "fg-dpo": {
        "keywords": [
            "verwerkingsgrondslag",
            "DPIA",
            "rechten betrokkenen",
            "AVG Art 38",
            "privacy by design",
            "bijzondere persoonsgegevens",
            "functionaris gegevensbescherming",
        ],
        "source_types": ["regulation"],
        "content_types": ["regulatory"],
    },
    "privacy": {
        "keywords": [
            "privacy by design",
            "data minimization",
            "verwerkingsregister",
            "consent",
            "privacy impact",
        ],
        "source_types": ["regulation", "policy"],
        "content_types": ["regulatory", "policy"],
    },
    "solution": {
        "keywords": [
            "technical feasibility",
            "NFR",
            "implementation",
            "migration",
            "non-functional requirements",
        ],
        "source_types": ["policy", "vendor", "archimate"],
        "content_types": ["vendor", "archimate", "policy"],
    },
    "information": {
        "keywords": [
            "information ownership",
            "WGBO",
            "retention",
            "data lineage",
            "records management",
            "informatiebeheer",
        ],
        "source_types": ["regulation", "policy"],
        "content_types": ["regulatory", "policy"],
    },
    "network": {
        "keywords": [
            "network segmentation",
            "firewall",
            "VPN",
            "DICOM networking",
            "Cloverleaf connectivity",
            "netwerkarchitectuur",
        ],
        "source_types": ["policy", "standard", "archimate"],
        "content_types": ["archimate", "policy"],
    },
    "portfolio": {
        "keywords": [
            "roadmap alignment",
            "capacity planning",
            "sequencing",
            "dependency management",
            "portfolio",
        ],
        "source_types": ["policy", "archimate"],
        "content_types": ["archimate", "policy"],
    },
    "redteam": {
        "keywords": [
            "failure scenario",
            "assumption",
            "groupthink",
            "pre-mortem",
            "challenge",
            "risk blind spot",
        ],
        "source_types": ["policy", "standard"],
        "content_types": ["regulatory", "policy"],
    },
}


@dataclass
class PersonaContext:
    persona_id: str
    persona_name: str
    query: str
    augmented_query: str
    results: list[SearchResult] = field(default_factory=list)
    context_text: str = ""
    source_ids: list[str] = field(default_factory=list)
    query_intent: QueryIntent = QueryIntent.HYBRID
    alpha: float = 0.5
    version_warnings: list[str] = field(default_factory=list)


async def retrieve_per_persona(
    request: str,
    selected_perspectives: list[str],
    embedding_router: EmbeddingRouter,
    store: VectorStoreClient,
    top_k_per_persona: int = 15,
    reranker: Reranker | None = None,
    use_hyde: bool = False,
) -> list[PersonaContext]:
    """Retrieve context bundles for each selected persona.

    Each persona's domain keywords augment their query, and their
    content_types and source_types filter retrieval results.
    When a reranker is provided, results are cross-encoded after initial
    retrieval for higher accuracy. When use_hyde is True, a hypothetical
    answer is generated to improve embedding quality.
    """
    contexts: list[PersonaContext] = []
    _reranker = reranker or IdentityReranker()

    for perspective_id in selected_perspectives:
        domain_info = PERSONA_DOMAINS.get(perspective_id, {})
        keywords = domain_info.get("keywords", [perspective_id])
        persona_name = _get_persona_name(perspective_id)
        content_types = domain_info.get("content_types", ["regulatory"])

        # Classify query to determine hybrid alpha
        classified = classify_query(request, perspective_id)
        augmented_query = f"{request} {' '.join(classified.expanded.split()[:20] if len(classified.expanded.split()) > len(request.split()) else keywords)}"

        # HyDE: generate hypothetical answer for better embedding match
        hyde_text = augmented_query
        if use_hyde and hasattr(_reranker, "generate_hypothetical"):
            try:
                hyde_text = await _reranker.generate_hypothetical(
                    request,
                    persona_id=perspective_id,
                    persona_focus=domain_info.get("focus", ""),
                )
            except Exception:
                pass

        try:
            query_vector = await embedding_router.embed_query_for_type(
                hyde_text, content_types[0] if content_types else "regulatory"
            )
        except Exception:
            try:
                query_vector = await embedding_router._default.embed_query(hyde_text)
            except Exception:
                contexts.append(
                    PersonaContext(
                        persona_id=perspective_id,
                        persona_name=persona_name,
                        query=request,
                        augmented_query=augmented_query,
                        context_text="",
                        query_intent=classified.intent,
                        alpha=classified.alpha,
                    )
                )
                continue

        persona_domains_list = keywords
        fetch_k = top_k_per_persona * 5 if reranker else top_k_per_persona

        try:
            results = await store.search_persona(
                query_vector=query_vector,
                query_text=augmented_query,
                persona_id=perspective_id,
                persona_domains=persona_domains_list,
                top_k=fetch_k,
                alpha=classified.alpha,
            )
        except Exception:
            results = []

        if reranker and len(results) > top_k_per_persona:
            try:
                results = await reranker.rerank(augmented_query, results, top_k_per_persona)
            except Exception:
                results = results[:top_k_per_persona]

        context_parts: list[str] = []
        source_ids: list[str] = []
        seen_parents: set[str] = set()
        for r in results:
            display_content = _cleanup_enrichment(r.content)
            display_prefix = _cleanup_enrichment(r.context_prefix)
            contextual_header = ""
            if display_prefix:
                contextual_header = f"{display_prefix}\n"

            if r.parent_content and r.parent_id and r.parent_id not in seen_parents:
                seen_parents.add(r.parent_id)
                max_parent = r.parent_content[:2000]
                context_parts.append(
                    f"[§K:{r.source_id}|§P:{r.parent_id}] [Parent Context]\n{max_parent}"
                )

            chapter_info = ""
            if r.chapter_title:
                chapter_info = f" (Hoofdstuk {r.chapter_num}: {r.chapter_title})"

            context_parts.append(
                f"[§K:{r.source_id}]{chapter_info} {contextual_header}{display_content}"
            )
            if r.source_id not in source_ids:
                source_ids.append(r.source_id)

        context_text = "\n\n---\n\n".join(context_parts) if context_parts else ""

        version_warnings: list[str] = []
        source_versions: dict[str, set[str]] = {}
        for r in results:
            if r.versie and r.source_id:
                source_versions.setdefault(r.source_id, set()).add(r.versie)
        for sid, versions in source_versions.items():
            if len(versions) > 1:
                version_warnings.append(
                    f"CONFLICT: {sid} has versions {sorted(versions)} — results may mix outdated and current rules"
                )

            contexts.append(
                PersonaContext(
                    persona_id=perspective_id,
                    persona_name=persona_name,
                    query=request,
                    augmented_query=augmented_query,
                    results=results,
                    context_text=context_text,
                    source_ids=source_ids,
                    query_intent=classified.intent,
                    alpha=classified.alpha,
                    version_warnings=version_warnings,
                )
            )

    return contexts


def build_retrieved_context_for_prompt(
    persona_contexts: list[PersonaContext],
) -> dict[str, str]:
    """Convert PersonaContext list to the dict format expected by the prompt builder.

    Returns {perspective_id: context_text} for injection into the assessment prompt.
    """
    return {ctx.persona_id: ctx.context_text for ctx in persona_contexts if ctx.context_text}


def _get_persona_name(perspective_id: str) -> str:
    from preflight.llm.prompt import PERSPECTIVES

    for p in PERSPECTIVES:
        if p["id"] == perspective_id:
            return p["label"]
    return perspective_id
