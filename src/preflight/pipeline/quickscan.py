"""
Quick Scan — 30-second lightweight check before full assessment.

Runs classification + triage floors + red-flag detection WITHOUT calling
the LLM for assessment. Tells the architect whether to:
  - PROCEED: low-risk, standard path, no obvious blockers
  - PROCEED_WITH_CAUTION: some flags, full assessment recommended
  - STOP_AND_ASSESS: hard triage floor hit, mandatory deep assessment

FIRST PRINCIPLE: Quick Scan must be FAST. No LLM calls for assessment.
Only uses: heuristic classification + triage floor rules + keyword red-flags.

INVERSION: What if Quick Scan says "proceed" but it's actually complex?
  → Quick Scan can NEVER downgrade a triage floor. It adds warnings, never removes them.
  → False-PROCEED is acceptable; False-STOP is not (it wastes time but is safe).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from preflight.classify.classify import (
    ClassificationResult,
    _heuristic_classify,
    select_relevant_perspectives,
)
from preflight.pipeline.pipeline import apply_triage_floors


class QuickScanVerdict(str, Enum):
    PROCEED = "PROCEED"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    STOP_AND_ASSESS = "STOP_AND_ASSESS"


@dataclass
class QuickScanResult:
    verdict: QuickScanVerdict
    classification: ClassificationResult
    triage: dict = field(default_factory=dict)
    perspectives: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_assessment_time: str = "2-3 minutes (fast) / 15-20 minutes (deep)"
    recommendation: str = ""


_RED_FLAG_PATTERNS: list[tuple[str, str]] = [
    (
        "clinical-system",
        "clinical-system",
        "Triggers mandatory CMIO review — cannot fast-track",
    ),
    (
        "patient-data",
        "patient-data",
        "Patient data processing — FG-DPO must be activated",
    ),
    (
        "ai-ml",
        "ai-ml",
        "AI/ML system — EU AI Act classification required, cannot fast-track",
    ),
]

_STOP_KEYWORDS = frozenset(
    {
        "levenskritiek",
        "life-critical",
        "intensive care",
        "intensivecare",
        "medisch device",
        "medical device",
        "mdr",
        "ivdr",
        "implantaat",
        "implant",
    }
)

_CAUTION_KEYWORDS = frozenset(
    {
        "patiëntdata",
        "patient data",
        "persoonsgegevens",
        "bsn",
        "ai",
        "machine learning",
        "algoritme",
        "koppeling",
        "integration",
        "hl7",
        "fhir",
        "vendor",
        "leverancier",
        "saas",
        "cloud",
        "extern",
    }
)


def quick_scan(request: str) -> QuickScanResult:
    classification = _heuristic_classify(request)

    _DEFAULT_TREATMENT = {
        "low": "fast-track",
        "medium": "standard-review",
        "high": "standard-review",
        "critical": "deep-review",
    }
    default_treatment = _DEFAULT_TREATMENT.get(classification.impact_level, "standard-review")

    perspectives = select_relevant_perspectives(
        classification.request_type, classification.impact_level
    )
    triage = {
        "treatment": default_treatment,
        "reason": f"Default for {classification.impact_level} impact",
    }
    perspectives, triage = apply_triage_floors(
        classification.request_type,
        classification.impact_level,
        perspectives,
        triage,
        request_text=request,
    )

    red_flags: list[str] = []
    warnings: list[str] = []
    lower = request.lower()

    for pattern, flag_type, message in _RED_FLAG_PATTERNS:
        if (
            pattern in lower
            or pattern == classification.request_type
            or pattern == classification.impact_level
        ):
            red_flags.append(f"[{flag_type}] {message}")

    for kw in _STOP_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            red_flags.append(f"[stop-keyword] '{kw}' detected — mandatory deep assessment")

    for kw in _CAUTION_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            warnings.append(f"Caution: '{kw}' detected — may require additional review")

    if triage.get("treatment") != "standard-review":
        red_flags.append(f"[triage-floor] {triage.get('reason', 'Non-standard triage applied')}")

    if classification.impact_level == "critical":
        red_flags.append("[impact] Critical impact — cannot fast-track")

    verdict = _determine_verdict(classification, triage, red_flags, warnings)

    est_time = "2-3 minutes (fast mode)"
    if verdict == QuickScanVerdict.STOP_AND_ASSESS:
        est_time = "15-20 minutes (deep mode mandatory)"
    elif verdict == QuickScanVerdict.PROCEED_WITH_CAUTION:
        est_time = "5-8 minutes (fast with additional review)"

    recommendation = _build_recommendation(verdict, classification, red_flags)

    return QuickScanResult(
        verdict=verdict,
        classification=classification,
        triage=triage,
        perspectives=perspectives,
        red_flags=red_flags,
        warnings=warnings,
        estimated_assessment_time=est_time,
        recommendation=recommendation,
    )


def _determine_verdict(
    classification: ClassificationResult,
    triage: dict,
    red_flags: list[str],
    warnings: list[str],
) -> QuickScanVerdict:
    if red_flags:
        return QuickScanVerdict.STOP_AND_ASSESS

    if (
        classification.impact_level in ("high", "critical")
        or triage.get("treatment") != "standard-review"
    ):
        return QuickScanVerdict.STOP_AND_ASSESS

    if warnings or classification.confidence < 0.6:
        return QuickScanVerdict.PROCEED_WITH_CAUTION

    return QuickScanVerdict.PROCEED


def _build_recommendation(
    verdict: QuickScanVerdict,
    classification: ClassificationResult,
    red_flags: list[str],
) -> str:
    if verdict == QuickScanVerdict.PROCEED:
        return (
            f"Low-risk {classification.request_type} request. Standard fast assessment recommended."
        )
    if verdict == QuickScanVerdict.PROCEED_WITH_CAUTION:
        return (
            f"Some flags detected for {classification.request_type} request. "
            f"Run full assessment with careful review of warnings."
        )
    return (
        f"HIGH-RISK: {classification.request_type}/{classification.impact_level}. "
        f"{len(red_flags)} red flag(s). Deep assessment MANDATORY — "
        f"fast-track is not permitted."
    )
