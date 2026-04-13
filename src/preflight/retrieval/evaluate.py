"""
Preflight RAG evaluation — per-persona retrieval quality metrics.

Measures what matters: does each persona get relevant context?
Not generic RAG metrics — persona-specific ones.

Four metrics (inspired by RAGAS but purpose-built):
  1. Context Precision: does persona X retrieve ITS domain content?
  2. Context Recall: did persona X find ALL relevant chunks?
  3. Citation Faithfulness: are findings grounded in retrieved sources?
  4. Cross-Persona Contamination: Victor should NOT get Aisha's privacy docs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from preflight.retrieval.retrieve import PersonaContext, PERSONA_DOMAINS


@dataclass
class PersonaRetrievalMetrics:
    persona_id: str
    persona_name: str
    num_results: int = 0
    num_relevant: int = 0
    precision: float = 0.0
    recall: float = 0.0
    source_diversity: int = 0
    contamination_count: int = 0
    contamination_rate: float = 0.0
    avg_score: float = 0.0


@dataclass
class RAGEvalReport:
    total_personas: int = 0
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_contamination: float = 0.0
    faithfulness: float = 1.0
    persona_metrics: list[PersonaRetrievalMetrics] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def evaluate_per_persona(
    persona_contexts: list[PersonaContext],
    expected_sources: dict[str, list[str]] | None = None,
    citation_report=None,
) -> RAGEvalReport:
    """Evaluate RAG quality per persona.

    Args:
        persona_contexts: what each persona actually retrieved
        expected_sources: {persona_id: [source_ids that SHOULD be found]}
        citation_report: from preflight.citation.verify.build_citation_report
    """
    if not persona_contexts:
        return RAGEvalReport(warnings=["No persona contexts to evaluate"])

    expected = expected_sources or {}
    metrics: list[PersonaRetrievalMetrics] = []

    for ctx in persona_contexts:
        m = PersonaRetrievalMetrics(
            persona_id=ctx.persona_id,
            persona_name=ctx.persona_name,
            num_results=len(ctx.results),
        )

        if not ctx.results:
            metrics.append(m)
            continue

        scores = [r.score for r in ctx.results if r.score > 0]
        m.avg_score = sum(scores) / len(scores) if scores else 0.0
        m.source_diversity = len(set(r.source_id for r in ctx.results))

        domain_keywords = PERSONA_DOMAINS.get(ctx.persona_id, {}).get("keywords", [])
        for r in ctx.results:
            content_lower = r.content.lower()
            if any(kw.lower() in content_lower for kw in domain_keywords):
                m.num_relevant += 1

        m.precision = m.num_relevant / m.num_results if m.num_results else 0.0

        if ctx.persona_id in expected:
            expected_set = set(expected[ctx.persona_id])
            found_set = set(r.source_id for r in ctx.results)
            hits = expected_set & found_set
            m.recall = len(hits) / len(expected_set) if expected_set else 1.0
        else:
            m.recall = 1.0

        other_domains: set[str] = set()
        for pid, dinfo in PERSONA_DOMAINS.items():
            if pid != ctx.persona_id:
                other_domains.update(kw.lower() for kw in dinfo.get("keywords", []))

        own_domains = set(kw.lower() for kw in domain_keywords)
        exclusive_others = other_domains - own_domains

        for r in ctx.results:
            content_lower = r.content.lower()
            if any(kw in content_lower for kw in exclusive_others):
                if not any(kw in content_lower for kw in own_domains):
                    m.contamination_count += 1

        m.contamination_rate = (
            m.contamination_count / m.num_results if m.num_results else 0.0
        )

        if m.precision < 0.3 and m.num_results > 0:
            metrics.append(m)
            continue

        metrics.append(m)

    faithfulness = 1.0
    if citation_report:
        faithfulness = citation_report.faithfulness_score

    precisions = [m.precision for m in metrics if m.num_results > 0]
    recalls = [m.recall for m in metrics if m.num_results > 0]
    contams = [m.contamination_rate for m in metrics if m.num_results > 0]

    warnings = []
    for m in metrics:
        if m.num_results == 0:
            warnings.append(f"{m.persona_id}: no results retrieved")
        if m.contamination_rate > 0.5:
            warnings.append(
                f"{m.persona_id}: {m.contamination_rate:.0%} results from other domains"
            )
        if m.precision < 0.3 and m.num_results > 3:
            warnings.append(f"{m.persona_id}: low precision ({m.precision:.0%})")

    return RAGEvalReport(
        total_personas=len(metrics),
        avg_precision=sum(precisions) / len(precisions) if precisions else 0.0,
        avg_recall=sum(recalls) / len(recalls) if recalls else 0.0,
        avg_contamination=sum(contams) / len(contams) if contams else 0.0,
        faithfulness=faithfulness,
        persona_metrics=metrics,
        warnings=warnings,
    )
