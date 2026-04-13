"""
Step 1: Classify — determine request type + impact level from a business request.

Uses an LLM call to categorize the request against known request types
and assess its impact level. This drives persona selection (ROUTING),
triage floors, and required document set.

Design decisions:
- Classification is the FIRST LLM call — must be fast and reliable
- Output is structured JSON, parsed with strict + fallback strategies
- Low temperature (0.1) — classification should be deterministic
- Landscape context from Step 0 is included to ground the LLM
- If LLM fails, falls back to keyword heuristic (never blocks the pipeline)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from preflight.llm.client import LLMClient, LLMRouter, CallOpts


# ---------------------------------------------------------------------------
# Known request types (must match ROUTING keys in ea-council-personas)
# ---------------------------------------------------------------------------

REQUEST_TYPES = [
    "new-application",
    "vendor-selection",
    "infrastructure-change",
    "integration",
    "data-platform",
    "clinical-system",
    "manufacturing-ot",
    "rnd-engineering",
    "ai-ml",
    "decommission",
    "patient-data",
    "architecture-roadmap",
    "capability-assessment",
]

IMPACT_LEVELS = ["low", "medium", "high", "critical"]

REQUEST_TYPE_DESCRIPTIONS = {
    "new-application": "Introducing a new software application or SaaS solution into the hospital landscape",
    "vendor-selection": "Evaluating and selecting a vendor for an existing or new capability",
    "infrastructure-change": "Changes to servers, networks, cloud, or platform infrastructure",
    "integration": "Adding or modifying interfaces, data flows, or middleware between systems",
    "data-platform": "Data warehouse, analytics platform, BI tool, or data lake changes",
    "clinical-system": "Any system directly involved in patient care: HIS, LIS, PACS, EPR, PACS, medication, decision support",
    "manufacturing-ot": "IT/OT convergence, factory floor, SCADA, MES, production systems",
    "rnd-engineering": "R&D tools, CAD/CAE, PLM, simulation, HPC for engineering",
    "ai-ml": "Artificial intelligence or machine learning system, predictive analytics, clinical AI",
    "decommission": "Retiring or decommissioning an existing system or application",
    "patient-data": "Any proposal that primarily involves processing, storing, or sharing patient data",
    "architecture-roadmap": "Strategic architecture planning, roadmap updates, capability gap analysis",
    "capability-assessment": "Assessing current capability maturity or coverage against reference model",
}


# ---------------------------------------------------------------------------
# Classification prompt
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """You are an Enterprise Architecture intake classifier for a Dutch hospital. Your job is to categorize business requests accurately so the right board members review the proposal.

You MUST respond with ONLY a JSON object — no explanation, no markdown, no code fences. Format:

{
  "request_type": "<one of the types below>",
  "impact_level": "<low|medium|high|critical>",
  "confidence": 0.0-1.0,
  "keywords": ["list", "of", "domain", "keywords"],
  "summary_nl": "<1-sentence Dutch summary>",
  "summary_en": "<1-sentence English summary>",
  "reasoning": "<why this type and impact>"
}

Available request types:"""

_CLASSIFY_SYSTEM_TYPES = "\n".join(f'  - "{k}": {v}' for k, v in REQUEST_TYPE_DESCRIPTIONS.items())

_IMPACT_GUIDANCE = """
Impact level guidance:
  - low: Minor change, no patient data, no clinical workflow impact, single department
  - medium: New application or moderate integration, limited patient data exposure, 1-2 departments
  - high: Clinical system, significant patient data, cross-department impact, security implications
  - critical: Life-critical system, large-scale patient data, regulatory risk (MDR/IVDR), hospital-wide impact

TRIAGE FLOORS (these are hard rules, not suggestions):
  - If the request involves clinical care or patient treatment workflows → MUST be "clinical-system" type, impact >= high
  - If the request involves patient data (persoonsgegevens, zorggegevens) → MUST activate patient-data concerns, impact >= medium
  - If the request involves AI/ML for clinical decisions → MUST be "ai-ml" type, impact >= high
"""


def _build_classify_prompt(request: str, landscape_context: dict | None = None) -> tuple[str, str]:
    system = _CLASSIFY_SYSTEM + "\n" + _CLASSIFY_SYSTEM_TYPES + "\n" + _IMPACT_GUIDANCE

    user_parts = [f"Business request:\n{request}"]
    if landscape_context:
        existing = landscape_context.get("existingApps", [])
        if existing:
            user_parts.append(f"Existing applications in this space: {', '.join(existing)}")
        risks = landscape_context.get("openRisks", [])
        if risks:
            user_parts.append(f"Known risks in this domain: {'; '.join(risks)}")

    user_parts.append("Respond with ONLY the JSON object.")
    return system, "\n\n".join(user_parts)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    request_type: str
    impact_level: str
    confidence: float = 0.0
    keywords: list[str] = field(default_factory=list)
    summary_nl: str = ""
    summary_en: str = ""
    reasoning: str = ""
    method: str = "llm"
    dual: bool = False
    divergence: str | None = None


@dataclass
class DualClassificationResult:
    primary: ClassificationResult
    secondary: ClassificationResult | None = None
    agreement: bool = True
    divergence_type: str | None = None
    divergence_detail: str | None = None

    @property
    def merged(self) -> ClassificationResult:
        if self.secondary is None or self.agreement:
            result = ClassificationResult(
                request_type=self.primary.request_type,
                impact_level=self.primary.impact_level,
                confidence=max(
                    self.primary.confidence,
                    self.secondary.confidence if self.secondary else 0.0,
                ),
                keywords=list(
                    set(self.primary.keywords + (self.secondary.keywords if self.secondary else []))
                ),
                summary_nl=self.primary.summary_nl,
                summary_en=self.primary.summary_en,
                reasoning=self.primary.reasoning,
                method="llm-dual-agree" if self.agreement else "llm-dual-disagree",
            )
            return result

        merged_type = self.primary.request_type
        merged_impact = self.primary.impact_level
        if self.secondary.impact_level in (
            "high",
            "critical",
        ) and self.primary.impact_level not in ("high", "critical"):
            merged_impact = self.secondary.impact_level
        if self.secondary.impact_level == "critical" and self.primary.impact_level != "critical":
            merged_impact = "critical"

        merged_confidence = max(self.primary.confidence, self.secondary.confidence) * 0.7

        return ClassificationResult(
            request_type=merged_type,
            impact_level=merged_impact,
            confidence=merged_confidence,
            keywords=list(set(self.primary.keywords + self.secondary.keywords)),
            summary_nl=self.primary.summary_nl,
            summary_en=self.primary.summary_en,
            reasoning=f"Primary: {self.primary.reasoning} | Secondary: {self.secondary.reasoning}",
            method="llm-dual-disagree",
            dual=True,
            divergence=self.divergence_type,
        )


async def classify_request(
    client: LLMClient | LLMRouter,
    request: str,
    landscape_context: dict | None = None,
) -> ClassificationResult:
    system, user = _build_classify_prompt(request, landscape_context)

    actual_client = client.light() if isinstance(client, LLMRouter) else client
    opts = CallOpts(temperature=0.1, max_tokens=512, retries=2)

    try:
        response = await actual_client.call(system, user, opts)
        return _parse_classification(response.text)
    except Exception:
        return _heuristic_classify(request)


_STRICT_IMPACT_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


async def classify_request_dual(
    client: LLMClient | LLMRouter,
    request: str,
    landscape_context: dict | None = None,
) -> DualClassificationResult:
    import asyncio as _asyncio

    actual_client = client.light() if isinstance(client, LLMRouter) else client
    system, user = _build_classify_prompt(request, landscape_context)

    opts_a = CallOpts(temperature=0.1, max_tokens=512, retries=2)
    opts_b = CallOpts(temperature=0.3, max_tokens=512, retries=2)

    try:
        responses = await _asyncio.gather(
            actual_client.call(system, user, opts_a),
            actual_client.call(system, user, opts_b),
            return_exceptions=True,
        )
    except Exception:
        return DualClassificationResult(primary=_heuristic_classify(request))

    results = []
    for resp in responses:
        if isinstance(resp, Exception):
            results.append(None)
        else:
            try:
                results.append(_parse_classification(resp.text))
            except Exception:
                results.append(None)

    primary = results[0] or results[1] or _heuristic_classify(request)
    secondary = results[1] if results[1] is not None else None

    if secondary is None:
        return DualClassificationResult(primary=primary)

    type_agree = primary.request_type == secondary.request_type
    impact_agree = primary.impact_level == secondary.impact_level

    if type_agree and impact_agree:
        return DualClassificationResult(
            primary=primary,
            secondary=secondary,
            agreement=True,
        )

    divergence_type = None
    if not type_agree and not impact_agree:
        divergence_type = "both"
    elif not type_agree:
        divergence_type = "type"
    else:
        divergence_type = "impact"

    divergence_detail = ""
    if not type_agree:
        divergence_detail += f"type: {primary.request_type} vs {secondary.request_type}"
    if not impact_agree:
        if divergence_detail:
            divergence_detail += "; "
        divergence_detail += f"impact: {primary.impact_level} vs {secondary.impact_level}"

    return DualClassificationResult(
        primary=primary,
        secondary=secondary,
        agreement=False,
        divergence_type=divergence_type,
        divergence_detail=divergence_detail,
    )


def _parse_classification(text: str) -> ClassificationResult:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not json_match:
            return _heuristic_classify(text)
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return _heuristic_classify(text)

    request_type = data.get("request_type", "new-application")
    if request_type not in REQUEST_TYPES:
        closest = _closest_request_type(request_type)
        request_type = closest

    impact_level = data.get("impact_level", "medium").lower()
    if impact_level not in IMPACT_LEVELS:
        impact_level = "medium"

    return ClassificationResult(
        request_type=request_type,
        impact_level=impact_level,
        confidence=min(1.0, max(0.0, float(data.get("confidence", 0.7)))),
        keywords=data.get("keywords", []),
        summary_nl=data.get("summary_nl", ""),
        summary_en=data.get("summary_en", ""),
        reasoning=data.get("reasoning", ""),
        method="llm",
    )


# ---------------------------------------------------------------------------
# Heuristic fallback — keyword matching when LLM is unavailable
# ---------------------------------------------------------------------------

_CLINICAL_KEYWORDS = frozenset(
    {
        "his",
        "lis",
        "epd",
        "ezis",
        "pacs",
        "medication",
        "mediwatch",
        "patient care",
        "patiëntenzorg",
        "clinical",
        "klinisch",
        "behandeling",
        "diagnostiek",
        "diagnostics",
        "beslissondersteuning",
        "decision support",
        "jivex",
        "cloverleaf",
        "hl7v2",
        "fhir",
    }
)

_PATIENT_DATA_KEYWORDS = frozenset(
    {
        "patient data",
        "persoonsgegevens",
        "zorggegevens",
        "patiëntdata",
        "avg",
        "gdpr",
        "dpia",
        "privacy",
        "fg",
        "functionaris gegevensverwerking",
        "bsn",
        "burger service nummer",
        "medische data",
        "health data",
    }
)

_AI_ML_KEYWORDS = frozenset(
    {
        "ai",
        "ml",
        "machine learning",
        "artificial intelligence",
        "deep learning",
        "predictive",
        "algoritme",
        "algorithm",
        "neural network",
        "nlp",
        "computer vision",
        "large language model",
        "llm",
        "classification model",
    }
)

_INTEGRATION_KEYWORDS = frozenset(
    {
        "interface",
        "integratie",
        "koppeling",
        "hl7",
        "fhir",
        "api",
        "cloverleaf",
        "middleware",
        "data flow",
        "gegevensuitwisseling",
    }
)

_INFRASTRUCTURE_KEYWORDS = frozenset(
    {
        "server",
        "network",
        "netwerk",
        "cloud",
        "infrastructure",
        "infrastructuur",
        "vmware",
        "kubernetes",
        "container",
        "datacenter",
        "firewall",
        "dns",
        "load balancer",
        "backup",
        "storage",
        "san",
        "vpn",
        "zero-trust",
        "ztn",
        "remote access",
        "migration",
        "migratie",
        "replace",
        "overstap",
    }
)

_VENDOR_KEYWORDS = frozenset(
    {
        "vendor",
        "leverancier",
        "saas",
        "licentie",
        "license",
        "contract",
        "evaluatie",
        "evaluation",
        "rfp",
        "tender",
        "aanbesteding",
    }
)

_DECOMMISSION_KEYWORDS = frozenset(
    {
        "decommission",
        "uitfaseren",
        "afschaft",
        "retire",
        "sunset",
        "end-of-life",
        "eol",
        "uit dienst",
        "vervangen",
        "legacy",
    }
)

_DATA_PLATFORM_KEYWORDS = frozenset(
    {
        "data warehouse",
        "data lake",
        "bi",
        "business intelligence",
        "analytics",
        "reporting",
        "rapportage",
        "databricks",
        "snowflake",
        "power bi",
    }
)

_MANUFACTURING_KEYWORDS = frozenset(
    {
        "manufacturing",
        "ot",
        "scada",
        "mes",
        "productie",
        "factory",
        "isa-95",
        "iec 62443",
        "industrial",
        "plc",
    }
)

_RND_KEYWORDS = frozenset(
    {
        "rnd",
        "research",
        "onderzoek",
        "cad",
        "cae",
        "plm",
        "hpc",
        "simulation",
        "simulatie",
        "engineering",
    }
)

_ROADMAP_KEYWORDS = frozenset(
    {
        "roadmap",
        "strategie",
        "strategy",
        "target architecture",
        "doelarchitectuur",
        "transition architecture",
        "capability gap",
    }
)


def _heuristic_classify(request: str) -> ClassificationResult:
    lower = request.lower()
    keywords: list[str] = []

    request_type = "new-application"
    impact_level = "medium"

    type_keywords = {
        "clinical-system": _CLINICAL_KEYWORDS,
        "ai-ml": _AI_ML_KEYWORDS,
        "patient-data": _PATIENT_DATA_KEYWORDS,
        "manufacturing-ot": _MANUFACTURING_KEYWORDS,
        "rnd-engineering": _RND_KEYWORDS,
        "integration": _INTEGRATION_KEYWORDS,
        "data-platform": _DATA_PLATFORM_KEYWORDS,
        "decommission": _DECOMMISSION_KEYWORDS,
        "infrastructure-change": _INFRASTRUCTURE_KEYWORDS,
        "vendor-selection": _VENDOR_KEYWORDS,
        "architecture-roadmap": _ROADMAP_KEYWORDS,
    }

    best_type = "new-application"
    best_score = 0
    for rtype, kwset in type_keywords.items():
        score = sum(1 for kw in kwset if re.search(rf"\b{re.escape(kw)}\b", lower))
        if score > best_score:
            best_score = score
            best_type = rtype

    request_type = best_type
    keywords = [
        kw
        for kw in type_keywords.get(best_type, set())
        if re.search(rf"\b{re.escape(kw)}\b", lower)
    ]

    type_default_impact = {
        "clinical-system": "high",
        "ai-ml": "high",
        "patient-data": "medium",
        "manufacturing-ot": "high",
        "rnd-engineering": "medium",
        "integration": "medium",
        "data-platform": "medium",
        "decommission": "medium",
        "infrastructure-change": "medium",
        "vendor-selection": "medium",
        "architecture-roadmap": "low",
    }
    impact_level = type_default_impact.get(request_type, "medium")

    if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in _PATIENT_DATA_KEYWORDS):
        if impact_level == "low":
            impact_level = "medium"
        keywords.append("patient-data")

    if any(
        re.search(rf"\b{re.escape(kw)}\b", lower)
        for kw in (
            "kritiek",
            "levenskritiek",
            "life-critical",
            "intensive care",
            "intensivecare",
            "levensbedreigend",
        )
    ):
        impact_level = "critical"

    return ClassificationResult(
        request_type=request_type,
        impact_level=impact_level,
        confidence=0.5,
        keywords=keywords,
        summary_en=request[:100],
        summary_nl="",
        reasoning="Heuristic keyword classification (LLM unavailable)",
        method="heuristic",
    )


def _closest_request_type(raw: str) -> str:
    lower = raw.lower().replace(" ", "-").replace("_", "-")
    for rt in REQUEST_TYPES:
        if lower == rt:
            return rt
    for rt in REQUEST_TYPES:
        if rt.startswith(lower[:4]) or lower.startswith(rt[:4]):
            return rt
    return "new-application"


# ---------------------------------------------------------------------------
# Persona selection — port of ROUTING + selectRelevant from personas
# ---------------------------------------------------------------------------

ROUTING: dict[str, list[str]] = {
    "new-application": [
        "cio",
        "chief",
        "business",
        "process",
        "application",
        "integration",
        "infrastructure",
        "data",
        "information",
        "solution",
        "network",
        "security",
        "iso-officer",
        "risk",
        "fg-dpo",
        "privacy",
    ],
    "vendor-selection": [
        "cio",
        "chief",
        "application",
        "solution",
        "integration",
        "security",
        "ciso",
        "iso-officer",
        "risk",
        "fg-dpo",
        "privacy",
    ],
    "infrastructure-change": [
        "chief",
        "infrastructure",
        "network",
        "security",
        "iso-officer",
        "risk",
    ],
    "integration": [
        "chief",
        "integration",
        "application",
        "process",
        "information",
        "network",
        "security",
        "iso-officer",
        "risk",
    ],
    "data-platform": [
        "chief",
        "data",
        "information",
        "infrastructure",
        "network",
        "security",
        "iso-officer",
        "risk",
        "fg-dpo",
        "privacy",
    ],
    "clinical-system": [
        "cio",
        "cmio",
        "chief",
        "business",
        "process",
        "application",
        "integration",
        "information",
        "solution",
        "data",
        "network",
        "security",
        "ciso",
        "iso-officer",
        "risk",
        "fg-dpo",
        "privacy",
    ],
    "manufacturing-ot": [
        "chief",
        "manufacturing",
        "infrastructure",
        "network",
        "security",
        "iso-officer",
        "risk",
    ],
    "rnd-engineering": ["chief", "rnd", "infrastructure", "data", "security", "risk"],
    "ai-ml": [
        "cio",
        "chief",
        "data",
        "information",
        "application",
        "solution",
        "security",
        "ciso",
        "risk",
        "fg-dpo",
        "privacy",
    ],
    "decommission": [
        "chief",
        "application",
        "integration",
        "infrastructure",
        "information",
        "portfolio",
        "risk",
        "fg-dpo",
    ],
    "patient-data": [
        "cmio",
        "chief",
        "data",
        "information",
        "security",
        "ciso",
        "iso-officer",
        "risk",
        "fg-dpo",
        "privacy",
    ],
    "architecture-roadmap": [
        "chief",
        "portfolio",
        "business",
        "application",
        "infrastructure",
        "solution",
        "risk",
    ],
    "capability-assessment": [
        "chief",
        "portfolio",
        "business",
        "application",
        "data",
        "information",
        "risk",
    ],
}

CORE_ALWAYS = ["chief", "security", "risk", "fg-dpo"]

PERSPECTIVE_IDS = [
    "cio",
    "cmio",
    "chief",
    "business",
    "process",
    "application",
    "integration",
    "infrastructure",
    "data",
    "manufacturing",
    "rnd",
    "security",
    "risk",
    "redteam",
    "ciso",
    "iso-officer",
    "fg-dpo",
    "privacy",
    "solution",
    "information",
    "network",
    "portfolio",
]


def select_relevant_perspectives(
    request_type: str,
    impact_level: str = "medium",
) -> list[str]:
    selected = list(ROUTING.get(request_type, CORE_ALWAYS))

    if impact_level in ("high", "critical") and "redteam" not in selected:
        selected.append("redteam")

    if impact_level == "critical" and "cmio" not in selected:
        selected.append("cmio")

    return selected
