"""
Preflight query classification — route queries to keyword-heavy, semantic-heavy,
or blended retrieval based on query characteristics.

FIRST PRINCIPLE: Regulatory references (NEN 7510, AVG artikel 6) are EXACT terms
that keyword search finds better than semantic. Natural language questions
("what encryption standard do we need?") are SEMANTIC and need embedding search.
The wrong blend wastes retrieval budget.

SECOND ORDER: If we misclassify, keyword queries get semantic noise, semantic
queries get irrelevant NEN section references. The cost is retrieval quality —
wrong alpha = wrong results. Fallback: always use HYBRID (α=0.5).

INVERSION: What makes this fail? Over-engineering the classifier. Solution: a
simple rule-based system with regex for regulatory terms + a short NL question
detector. No LLM call needed — latency must be <1ms.

Pattern inspired by Onyx's QueryAnalysisModel, adapted for Dutch EA context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class QueryIntent(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class ClassifiedQuery:
    original: str
    expanded: str
    intent: QueryIntent
    alpha: float
    keywords: list[str]
    reasoning: str


REGULATORY_PATTERNS: list[tuple[str, str]] = [
    (r"NEN\s*(\d{4})", "ned_add"),
    (r"AVG|UAVG|GDPR|Algemene Verordening Gegevensbescherming", "keyword"),
    (r"artikel\s*\d+", "keyword"),
    (r"§\s*[\d.]+", "keyword"),
    (r"MDR|IVDR|2017/745|2022/986", "keyword"),
    (r"BSN|burgerservicenumummer", "keyword"),
    (r"NIS2?|Wegiz|AiVG", "keyword"),
    (r"ZiRA|Ziekenhuis Referentie Architectuur", "keyword"),
    (r"BIV|beschikbaarheid|integriteit|versletenheid", "keyword"),
    (r"encrypti|versleuteling|crypto", "keyword"),
    (r"§?P:\w+", "keyword"),
]

STRUCTURAL_QUERY_PATTERNS: list[tuple[str, str]] = [
    (r"^(wat|welke|hoe|waarom|wanneer|wie|welk)\b", "semantic"),
    (r"^(what|which|how|why|when|who)\b", "semantic"),
    (r"^(is|zijn|was|were|can|could|should|moet|kan|moet)\b", "semantic"),
    (r"\?", "semantic"),
]

DUTCH_STOPWORDS = frozenset(
    "de het een van in op aan met voor dat deze dit zij zijn hebben wordt "
    "ook nog al er toe dan om te niet maar wel".split()
)


def classify_query(query: str, persona_id: str = "") -> ClassifiedQuery:
    keyword_score = 0
    semantic_score = 0
    detected_keywords: list[str] = []

    for pattern, kind in REGULATORY_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            if kind == "keyword":
                keyword_score += 2
                match = re.search(pattern, query, re.IGNORECASE)
                detected_keywords.append(match.group(0))
            elif kind == "ned_add":
                keyword_score += 3
                match = re.search(pattern, query, re.IGNORECASE)
                detected_keywords.append(f"NEN {match.group(1)}")

    for pattern, kind in STRUCTURAL_QUERY_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            if kind == "semantic":
                semantic_score += 1

    if len(query.split()) <= 4 and not detected_keywords:
        semantic_score += 1

    PERSONA_KEYWORD_BIAS: dict[str, float] = {
        "data": -0.1,
        "fg-dpo": -0.1,
        "privacy": -0.1,
        "security": 0.2,
        "ciso": 0.2,
        "risk": 0.1,
        "redteam": 0.1,
    }
    if persona_id in PERSONA_KEYWORD_BIAS:
        keyword_score += PERSONA_KEYWORD_BIAS[persona_id] * 3

    reasoning_parts = []
    if keyword_score > semantic_score + 1:
        intent = QueryIntent.KEYWORD
        alpha = 0.2
        reasoning_parts.append(
            f"keyword_score={keyword_score} > semantic_score={semantic_score}"
        )
    elif semantic_score > keyword_score + 1:
        intent = QueryIntent.SEMANTIC
        alpha = 0.8
        reasoning_parts.append(
            f"semantic_score={semantic_score} > keyword_score={keyword_score}"
        )
    else:
        intent = QueryIntent.HYBRID
        alpha = 0.5
        reasoning_parts.append(
            f"balanced: keyword={keyword_score}, semantic={semantic_score}"
        )

    expanded_parts = [query]
    if detected_keywords:
        expanded_parts.extend(detected_keywords)
    domain_additions = _persona_domain_expansion(persona_id)
    if domain_additions:
        expanded_parts.extend(domain_additions[:3])

    return ClassifiedQuery(
        original=query,
        expanded=" ".join(expanded_parts),
        intent=intent,
        alpha=alpha,
        keywords=detected_keywords,
        reasoning="; ".join(reasoning_parts) if reasoning_parts else "default hybrid",
    )


def _persona_domain_expansion(persona_id: str) -> list[str]:
    from preflight.retrieval.retrieve import PERSONA_DOMAINS

    domain = PERSONA_DOMAINS.get(persona_id, {})
    return domain.get("keywords", [])[:3]
