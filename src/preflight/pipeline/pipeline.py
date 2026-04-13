"""
Preflight pipeline — triage, BIV, conditions, principetoets, verwerkingsregister.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from preflight.synthesis.engine import (
    generate_risk_register,
    generate_citation_appendix,
    citation_constraint_prompt,
)


# ---------------------------------------------------------------------------
# Request lifecycle
# ---------------------------------------------------------------------------

LIFECYCLE_STATES = [
    "SUBMITTED",
    "PRELIMINARY",
    "CLARIFICATION",
    "ASSESSED",
    "BOARD_READY",
    "IN_REVIEW",
    "DECIDED",
    "CONDITIONS_OPEN",
    "CLOSED",
]

VALID_TRANSITIONS = {
    "SUBMITTED": ["PRELIMINARY"],
    "PRELIMINARY": ["CLARIFICATION", "ASSESSED"],
    "CLARIFICATION": ["PRELIMINARY", "ASSESSED"],
    "ASSESSED": ["BOARD_READY", "CLARIFICATION"],
    "BOARD_READY": ["IN_REVIEW", "ASSESSED"],
    "IN_REVIEW": ["DECIDED"],
    "DECIDED": ["CONDITIONS_OPEN", "CLOSED"],
    "CONDITIONS_OPEN": ["CONDITIONS_OPEN", "CLOSED"],
    "CLOSED": [],
}


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in VALID_TRANSITIONS.get(from_state, [])


@dataclass
class AssessmentRequest:
    id: str
    state: str = "SUBMITTED"
    submitted_at: str = ""
    submitted_by: str = ""
    description: str = ""
    attachments: list[str] = field(default_factory=list)
    request_type: str = "new-application"
    impact_level: str = "medium"
    ratings: dict[str, str] = field(default_factory=dict)
    persona_findings: list[dict] = field(default_factory=list)
    triage: dict = field(default_factory=dict)
    biv: dict = field(default_factory=dict)
    zira: dict = field(default_factory=dict)
    landscape: dict = field(default_factory=dict)
    conditions: list[dict] = field(default_factory=list)
    documents: dict[str, str] = field(default_factory=dict)
    diagrams: dict = field(default_factory=dict)


def all_conditions_met(conditions: list[dict]) -> bool:
    return all(c.get("status") == "MET" for c in conditions)


# ---------------------------------------------------------------------------
# Triage floors — mandatory persona additions and treatment upgrades
# ---------------------------------------------------------------------------

TRIAGE_FLOORS = {
    "clinical-system": {
        "add_perspectives": ["cmio", "fg-dpo"],
        "minimum_treatment": "standard-review",
        "reason": "Clinical system requests always require CMIO and FG/DPO review",
    },
    "patient-data": {
        "add_perspectives": ["fg-dpo", "privacy"],
        "minimum_treatment": "standard-review",
        "reason": "Patient data requests always require FG/DPO and Privacy review",
    },
    "high": {
        "add_perspectives": ["redteam", "ciso"],
        "minimum_treatment": "standard-review",
        "reason": "High impact requests require Red Team and CISO review",
    },
    "critical": {
        "add_perspectives": ["redteam", "ciso", "risk"],
        "minimum_treatment": "deep-review",
        "reason": "Critical impact requests require deep review",
    },
    "decommission": {
        "add_perspectives": ["process", "business"],
        "minimum_treatment": "standard-review",
        "reason": "Decommissioning always requires process and business review",
    },
}

TREATMENT_LEVELS = {"fast-track": 0, "standard-review": 1, "deep-review": 2}

CROSS_TYPE_KEYWORDS = {
    "clinical-system": [
        "clinical",
        "klinisch",
        "patiënt",
        "zorg",
        "medisch",
        "diagnostiek",
        "HIS",
    ],
    "patient-data": [
        "patient data",
        "patiëntdata",
        "persoonsgegevens",
        "bsn",
        "zorggegevens",
        "EPD",
        "medical records",
    ],
}


def apply_triage_floors(
    request_type: str,
    impact_level: str,
    perspectives: list[str],
    triage: dict,
    request_text: str = "",
) -> tuple[list[str], dict]:
    perspective_set = set(perspectives)
    treatment = triage.get("treatment", "standard-review")
    treatment_level = TREATMENT_LEVELS.get(treatment, 1)

    if request_type in TRIAGE_FLOORS:
        floor = TRIAGE_FLOORS[request_type]
        for p in floor["add_perspectives"]:
            perspective_set.add(p)
        min_level = TREATMENT_LEVELS.get(floor["minimum_treatment"], 1)
        if min_level > treatment_level:
            treatment = floor["minimum_treatment"]
            treatment_level = min_level

    if impact_level in TRIAGE_FLOORS:
        floor = TRIAGE_FLOORS[impact_level]
        for p in floor["add_perspectives"]:
            perspective_set.add(p)
        min_level = TREATMENT_LEVELS.get(floor["minimum_treatment"], 1)
        if min_level > treatment_level:
            treatment = floor["minimum_treatment"]
            treatment_level = min_level

    cross_floors = _detect_cross_type_floors(request_text)
    for floor_key in cross_floors:
        if floor_key in TRIAGE_FLOORS:
            floor = TRIAGE_FLOORS[floor_key]
            for p in floor["add_perspectives"]:
                perspective_set.add(p)
            min_level = TREATMENT_LEVELS.get(floor["minimum_treatment"], 1)
            if min_level > treatment_level:
                treatment = floor["minimum_treatment"]
                treatment_level = min_level

    reasons = []
    if treatment != triage.get("treatment", "standard-review"):
        reasons.append(f"Triage upgraded to {treatment}")

    return sorted(perspective_set), {
        "treatment": treatment,
        "reason": "; ".join(reasons) or triage.get("reason", ""),
    }


def _detect_cross_type_floors(request_text: str) -> list[str]:
    if not request_text:
        return []
    lower = request_text.lower()
    matched = []
    for category, keywords in CROSS_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                matched.append(category)
                break
    return matched


# ---------------------------------------------------------------------------
# Authority actions — VETO, ESCALATION, INDEPENDENT, PATIENT_SAFETY
# ---------------------------------------------------------------------------

AUTHORITY_TYPES = {
    "security": {
        "type": "VETO",
        "trigger_rating": "block",
        "label": "Victor — Security Architecture",
    },
    "risk": {
        "type": "ESCALATION",
        "trigger_rating": "block",
        "label": "Nadia — Risk & Compliance",
    },
    "fg-dpo": {"type": "INDEPENDENT", "trigger_rating": "any", "label": "FG/DPO"},
    "cmio": {"type": "PATIENT_SAFETY", "trigger_rating": "concern", "label": "CMIO"},
}


def process_authority_actions(persona_findings: list[dict]) -> list[dict]:
    actions = []
    for pf in persona_findings:
        pid = pf.get("perspective_id", "")
        authority = pf.get("authority")
        if not authority:
            rule = AUTHORITY_TYPES.get(pid)
            if rule:
                authority = rule["type"]
        if not authority:
            continue

        rule = AUTHORITY_TYPES.get(pid, {})
        trigger_rating = rule.get("trigger_rating", "block")
        rating = pf.get("rating", "na")

        triggered = False
        if trigger_rating == "any":
            triggered = True
        elif trigger_rating == "block" and rating == "block":
            triggered = True
        elif trigger_rating == "concern" and rating in (
            "concern",
            "block",
            "conditional",
        ):
            triggered = True

        actions.append(
            {
                "type": authority,
                "persona": pid,
                "label": rule.get("label", pf.get("name", pid)),
                "triggered": triggered,
                "requires_sign_off": authority in ("VETO", "ESCALATION", "INDEPENDENT"),
                "sign_off_status": "PENDING" if triggered else "NOT_REQUIRED",
                "findings": pf.get("findings", []),
                "conditions": pf.get("conditions", []),
                "draft_disclaimer": (
                    "This is a DRAFT authority action generated by Preflight. "
                    "The designated authority persona must confirm before board presentation."
                ),
            }
        )
    return actions


# ---------------------------------------------------------------------------
# Conditions lifecycle
# ---------------------------------------------------------------------------


def create_conditions(
    persona_findings: list[dict],
    assessment_id: str,
    biv_controls: list[dict] | None = None,
) -> list[dict]:
    conditions = []
    from datetime import date as date_mod

    for pf in persona_findings:
        for cond in pf.get("conditions", []):
            if (
                isinstance(cond, str)
                and cond.strip()
                and cond.lower() not in ("none", "n/a", "geen", "-")
            ):
                conditions.append(
                    {
                        "assessment_id": assessment_id,
                        "condition_text": cond.strip(),
                        "source_persona": pf.get("name", pf.get("perspective_id", "")),
                        "source_perspective_id": pf.get("perspective_id", ""),
                        "status": "OPEN",
                        "due_date": None,
                        "met_date": None,
                        "waived_date": None,
                        "created_at": date_mod.today().isoformat(),
                    }
                )
            elif isinstance(cond, dict) and cond.get("condition", "").strip():
                conditions.append(
                    {
                        "assessment_id": assessment_id,
                        "condition_text": cond["condition"].strip(),
                        "source_persona": pf.get("name", pf.get("perspective_id", "")),
                        "source_perspective_id": pf.get("perspective_id", ""),
                        "status": "OPEN",
                        "due_date": None,
                        "met_date": None,
                        "waived_date": None,
                        "created_at": date_mod.today().isoformat(),
                    }
                )

    if biv_controls:
        for ctrl in biv_controls:
            conditions.append(
                {
                    "assessment_id": assessment_id,
                    "condition_text": f"[BIV] {ctrl.get('requirement', ctrl.get('standard', 'NEN 7510 control'))} — {ctrl.get('standard', '')}",
                    "source_persona": "BIV Analysis",
                    "source_perspective_id": "biv",
                    "status": "OPEN",
                    "due_date": None,
                    "met_date": None,
                    "waived_date": None,
                    "created_at": date_mod.today().isoformat(),
                }
            )

    return conditions


# ---------------------------------------------------------------------------
# BIV scoring
# ---------------------------------------------------------------------------


def determine_biv(persona_findings: list[dict], request_type: str) -> dict:
    b = 2
    i = 2
    v = 2

    is_clinical = request_type == "clinical-system"
    has_patient_data = request_type in ("patient-data", "clinical-system")

    if is_clinical:
        b = 3
    if has_patient_data:
        i = 3
        v = 3

    for pf in persona_findings:
        pf_biv = pf.get("biv", {})
        b = max(b, pf_biv.get("B", 0))
        i = max(i, pf_biv.get("I", 0))
        v = max(v, pf_biv.get("V", 0))

    rpo = {3: "≤1 uur", 2: "≤4 uur", 1: "≤24 uur"}.get(b, "≤24 uur")
    rto = {3: "≤4 uur", 2: "≤8 uur", 1: "≤24 uur"}.get(b, "≤24 uur")

    return {"B": b, "I": i, "V": v, "rpo": rpo, "rto": rto}


def derive_biv_controls(biv: dict) -> list[dict]:
    b, i, v = biv["B"], biv["I"], biv["V"]
    controls = []

    if b >= 3:
        controls += [
            {
                "requirement": "Disaster Recovery Plan mandatory",
                "standard": "NEN 7510",
                "reference": "B=3",
            },
            {"requirement": "RPO ≤ 1 hour", "standard": "BIA", "reference": "B=3"},
            {"requirement": "RTO ≤ 4 hours", "standard": "BIA", "reference": "B=3"},
            {
                "requirement": "Active-active or hot-standby architecture",
                "standard": "Architecture",
                "reference": "B=3",
            },
            {
                "requirement": "Annual DR test with documented results",
                "standard": "NEN 7510",
                "reference": "B=3",
            },
        ]
    elif b == 2:
        controls += [
            {"requirement": "RPO ≤ 4 hours", "standard": "BIA", "reference": "B=2"},
            {"requirement": "RTO ≤ 8 hours", "standard": "BIA", "reference": "B=2"},
            {
                "requirement": "Documented backup and restore procedures",
                "standard": "NEN 7510",
                "reference": "B=2",
            },
        ]

    if i >= 3:
        controls += [
            {
                "requirement": "Data validation mandatory on all data entry points",
                "standard": "NEN 7510",
                "reference": "I=3",
            },
            {
                "requirement": "NEN 7513 audit logging for all patient data access",
                "standard": "NEN 7513",
                "reference": "I=3",
            },
            {
                "requirement": "Data integrity checks (checksums, hash verification)",
                "standard": "Architecture",
                "reference": "I=3",
            },
            {
                "requirement": "Four-eyes principle for critical data modifications",
                "standard": "NEN 7510",
                "reference": "I=3",
            },
        ]
    elif i == 2:
        controls += [
            {
                "requirement": "Application-level data validation",
                "standard": "Architecture",
                "reference": "I=2",
            },
            {
                "requirement": "Audit logging for data modifications",
                "standard": "NEN 7510",
                "reference": "I=2",
            },
        ]

    if v >= 3:
        controls += [
            {
                "requirement": "NEN 7510 full scope compliance",
                "standard": "NEN 7510",
                "reference": "V=3",
            },
            {
                "requirement": "DPIA mandatory (AVG Article 35)",
                "standard": "AVG/GDPR",
                "reference": "V=3",
            },
            {
                "requirement": "Encryption at rest and in transit for all data",
                "standard": "NEN 7512",
                "reference": "V=3",
            },
            {
                "requirement": "NEN 7513 audit logging for all patient data access",
                "standard": "NEN 7513",
                "reference": "V=3",
            },
            {
                "requirement": "Access control based on least privilege (RBAC/ABAC)",
                "standard": "NEN 7510",
                "reference": "V=3",
            },
        ]
    elif v == 2:
        controls += [
            {
                "requirement": "Encryption in transit (TLS 1.2+)",
                "standard": "NEN 7512",
                "reference": "V=2",
            },
            {
                "requirement": "Access control (RBAC)",
                "standard": "NEN 7510",
                "reference": "V=2",
            },
            {
                "requirement": "DPIA assessment required",
                "standard": "AVG/GDPR",
                "reference": "V=2",
            },
        ]

    return controls


# ---------------------------------------------------------------------------
# ZiRA principetoets
# ---------------------------------------------------------------------------

ZIRA_PRINCIPLES = [
    (1, "Waardevol", "Waarde toevoegen, aansluiten bij organisatiedoelen"),
    (2, "Veilig en vertrouwd", "Veiligheid en privacy voorop"),
    (3, "Duurzaam", "Toekomstbestendig, verspilling vermijden"),
    (4, "Continu", "Continuiteit van zorg borgen"),
    (5, "Mens centraal", "De mens staat centraal"),
    (6, "Samen", "Afstemming met stakeholders"),
    (7, "Gestandaardiseerd", "Open standaarden en best practices"),
    (8, "Flexibel", "Modulair, uitbreidbaar, vervangbaar"),
    (9, "Eenvoudig", "Eenvoudigste oplossing die aan eisen voldoet"),
    (10, "Onder eigenaarschap", "Aangewezen eigenaren"),
    (11, "Datagedreven", "Gestructureerd voor hergebruik"),
    (12, "Innovatief", "Innovatie actief nastreven"),
]

_PRINCIPLE_PERSONA_MAP = {
    1: ["Sophie", "CIO"],
    2: ["Victor", "Nadia", "FG-DPO", "PO", "CISO", "ISO-Officer"],
    3: ["Daan", "Ruben"],
    4: ["Jan", "CMIO", "Aisha"],
    5: ["CMIO", "FG-DPO", "Aisha"],
    6: ["Joris", "Marco"],
    7: ["Thomas", "Lena"],
    8: ["Lena", "Thomas", "Marco"],
    9: ["Marcus", "Thomas"],
    10: ["CIO", "chief"],
    11: ["Aisha", "Daan"],
    12: ["Aisha", "CIO", "Sophie"],
}

_PRINCIPLE_DEFINITIONS = {
    1: "Draagt het voorstel bij aan de strategische doelen van de zorgorganisatie? Is het waardevol voor patiënten, medewerkers of procesverbetering?",
    2: "Is het voorstel veilig en privacy-vast? Voldoet het aan NEN 7510, AVG/GDPR, en is het risicomanagement adequaat?",
    3: "Is het voorstel toekomstbestendig? Vermindert het technische schuld? Is het duurzaam in onderhoud en exploitatie?",
    4: "Borgt het voorstel continuïteit van zorg? Is er een fallback, faalveiligheid, en acceptabel hersteltermijn?",
    5: "Staat de mens centraal? Zijn patiëntveiligheid, usability, en inclusiviteit gewaarborgd?",
    6: "Is er afgestemd met stakeholders? Zijn koppelingen, data-uitwisseling en governance geregeld?",
    7: "Gebruikt het voorstel open standaarden en best practices? Vermijdt het vendor lock-in?",
    8: "Is het voorstel modulair, uitbreidbaar en vervangbaar? Ondersteunt het architectuurprincipes zoals loose coupling?",
    9: "Is dit de eenvoudigste oplossing die aan de eisen voldoet? Is er geen simpeler alternatief?",
    10: "Zijn er aangewezen eigenaars voor het voorstel? Is eigenaarschap en beheer geregeld?",
    11: "Is het voorstel datagedreven? Zijn gegevens gestructureerd, vindbaar en herbruikbaar volgens FAIR-principes?",
    12: "Ondersteunt het voorstel innovatie? Is er ruiming voor experimentatie en schaalvergroting?",
}


def generate_principetoets(persona_findings: list[dict]) -> dict:
    ratings_map: dict[str, str] = {}
    for pf in persona_findings:
        name = pf.get("name", "")
        pid = pf.get("perspective_id", name.lower().replace(" ", "").replace("-", ""))
        rating = pf.get("rating", "na")
        ratings_map[pid] = rating
        ratings_map[name] = rating

    assessments = {}
    for num, principle_personas in _PRINCIPLE_PERSONA_MAP.items():
        principle_ratings = [
            ratings_map.get(p, ratings_map.get(p.lower().replace(" ", ""), "na"))
            for p in principle_personas
        ]
        has_block = "block" in principle_ratings
        has_concern = "concern" in principle_ratings
        has_conditional = "conditional" in principle_ratings
        has_approve = "approve" in principle_ratings

        if has_block:
            assessments[num] = "Niet"
        elif has_concern:
            assessments[num] = "Deels"
        elif has_conditional and not has_approve:
            assessments[num] = "Deels"
        elif has_approve and not has_concern and not has_conditional:
            assessments[num] = "Voldoet"
        elif has_conditional:
            assessments[num] = "Deels"
        else:
            assessments[num] = "N.v.t."

    rows = []
    satisfied = partial = unsatisfied = na = 0
    for num, name, desc in ZIRA_PRINCIPLES:
        assessment = assessments.get(num, "N.v.t.")
        definition = _PRINCIPLE_DEFINITIONS.get(num, "")
        toelichting = _get_principe_toelichting(num, persona_findings)
        if assessment == "Voldoet":
            satisfied += 1
        elif assessment == "Deels":
            partial += 1
        elif assessment == "Niet":
            unsatisfied += 1
        else:
            na += 1
        rows.append(f"| {num} | **{name}** — {desc} | {assessment} | {toelichting} |")

    table = (
        "| # | Principe | Beoordeling | Toelichting |\n|---|----------|-------------|-------------|\n"
        + "\n".join(rows)
    )
    summary = f"{satisfied} van 12 voldoet, {partial} deels, {unsatisfied} niet"
    return {
        "table": table,
        "summary": summary,
        "satisfied": satisfied,
        "partial": partial,
        "unsatisfied": unsatisfied,
        "principles": [
            {
                "number": num,
                "name": name,
                "description": desc,
                "definition": _PRINCIPLE_DEFINITIONS.get(num, ""),
                "assessment": assessments.get(num, "N.v.t."),
            }
            for num, name, desc in ZIRA_PRINCIPLES
        ],
    }


def _get_principe_toelichting(num: int, persona_findings: list[dict]) -> str:
    relevant = [
        pf
        for pf in persona_findings
        if num in _PRINCIPLE_PERSONA_MAP and pf.get("name") in _PRINCIPLE_PERSONA_MAP[num]
    ]
    if not relevant:
        return "[te beoordelen door architect]"
    return "; ".join(
        f"{pf['name']}: {pf.get('findings', [''])[0] if pf.get('findings') else pf.get('rating', '')}"
        for pf in relevant
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate_findings(persona_findings: list[dict]) -> dict:
    finding_map: dict[str, list[dict]] = {}
    for pf in persona_findings:
        if pf.get("rating") in ("approve", "na"):
            continue
        for finding in pf.get("findings", []):
            key = _normalize(finding)
            if key not in finding_map:
                finding_map[key] = []
            finding_map[key].append(
                {
                    "name": pf.get("name", ""),
                    "role": pf.get("role", ""),
                    "original": finding,
                }
            )

    consensus = []
    unique = []
    for key, sources in finding_map.items():
        if len(sources) >= 3:
            consensus.append(
                {
                    "finding": sources[0]["original"],
                    "raised_by": [s["name"] for s in sources],
                    "count": len(sources),
                }
            )
        else:
            for s in sources:
                unique.append(s["original"])

    return {"consensus": consensus, "unique": unique}


def _normalize(text: str) -> str:
    words = re.sub(r"[^a-z0-9\s]", "", text.lower()).split()
    return " ".join(sorted(w for w in words if len(w) > 3))


# ---------------------------------------------------------------------------
# Clarification questions
# ---------------------------------------------------------------------------


def generate_clarification_questions(
    request_description: str,
    landscape: dict | None = None,
    perspective_ids: list[str] | None = None,
) -> list[dict]:
    text = (request_description or "").lower()
    landscape = landscape or {}
    perspective_ids = perspective_ids or []
    questions = []

    signal_checks = [
        (
            [
                "patient",
                "patiënt",
                "zorg",
                "clinical",
                "klinisch",
                "medisch",
                "epd",
                "his",
            ],
            "Does this involve patient data or clinical systems?",
            ["CMIO", "FG-DPO", "Aisha"],
        ),
        (
            ["vendor", "leverancier", "saas", "contract", "aivg"],
            "Is this a new vendor/product selection?",
            ["Thomas", "Nadia"],
        ),
        (
            ["integrat", "koppel", "api", "interface", "hl7", "fhir", "cloverleaf"],
            "What systems does this need to integrate with?",
            ["Lena"],
        ),
        (
            ["cloud", "hosting", "on-prem", "datacenter", "azure", "aws"],
            "Where will this system run?",
            ["Jan"],
        ),
        (
            ["data", "persoonsgegevens", "gegevens", "privacy", "avg", "gdpr", "dpia"],
            "What data does this system process and where does it flow?",
            ["Aisha", "FG-DPO", "PO"],
        ),
        (
            ["budget", "cost", "kosten", "investering", "tco", "licentie"],
            "What is the budget and total cost of ownership?",
            ["CIO"],
        ),
        (
            ["security", "beveiliging", "nen 7510", "encryptie", "authenticatie"],
            "What are the security requirements?",
            ["Victor", "ISO-Officer"],
        ),
        (
            ["compliance", "regelgeving", "nis2", "mdr", "ivdr", "wegiz"],
            "Which regulatory frameworks apply?",
            ["Nadia"],
        ),
        (
            ["productie", "factory", "ot", "scada", "mes", "iec 62443"],
            "Does this touch the OT/manufacturing network?",
            ["Erik"],
        ),
        (
            ["ai", "machine learning", "algoritme", "model", "predict"],
            "Does this use AI or machine learning?",
            ["Aisha"],
        ),
    ]

    name_to_pid = {
        "CIO": "cio",
        "CMIO": "cmio",
        "Marcus": "chief",
        "Sophie": "business",
        "Joris": "process",
        "Thomas": "application",
        "Lena": "integration",
        "Jan": "infrastructure",
        "Aisha": "data",
        "Erik": "manufacturing",
        "Petra": "rnd",
        "Victor": "security",
        "CISO": "ciso",
        "ISO-Officer": "iso-officer",
        "Nadia": "risk",
        "FG-DPO": "fg-dpo",
        "PO": "privacy",
        "Marco": "solution",
        "Daan": "information",
        "Ruben": "network",
        "Femke": "portfolio",
        "Raven": "redteam",
    }

    for keywords, question, personas in signal_checks:
        if not any(kw in text for kw in keywords):
            relevant = [
                p
                for p in PERSONAS
                if p.get("name") in personas
                and (not perspective_ids or name_to_pid.get(p.get("name", "")) in perspective_ids)
            ]
            if relevant:
                questions.append(
                    {
                        "persona": relevant[0]["name"],
                        "role": relevant[0].get("role", ""),
                        "question": question,
                        "required": True,
                        "reason": f"Information not found in request. {relevant[0]['name']} needs this to assess the proposal.",
                    }
                )

    if not landscape.get("existingApps"):
        questions.append(
            {
                "persona": "Marcus",
                "role": "Chief Architect",
                "question": "No existing applications found in the capability space. Is the Archi model up to date for this domain?",
                "required": True,
                "reason": "Without landscape context, overlap detection and cascade analysis cannot be performed.",
            }
        )

    return questions


# ---------------------------------------------------------------------------
# Persona definitions (needed by clarification)
# ---------------------------------------------------------------------------

PERSONAS = [
    {
        "name": "CIO",
        "role": "CIO",
        "incentives": "IT strategy, budget, TCO, shadow-IT risk",
        "constraints": "No budget approval without ROI. No shadow IT.",
        "domain": ["budget", "strategy", "tco", "vendor", "saas"],
    },
    {
        "name": "CMIO",
        "role": "Clinical & Patient Safety",
        "incentives": "Patient safety, clinical workflows, HL7/FHIR compliance, MDR/IVDR",
        "constraints": "Cannot fast-track clinical systems. Patient safety is non-negotiable.",
        "domain": ["clinical", "patient", "hl7", "fhir", "dicom", "mdr", "ivdr"],
    },
    {
        "name": "Marcus",
        "role": "Chief Architect",
        "incentives": "ZiRA coherence, principetoets, architecture debt",
        "constraints": "Must follow ZiRA principles. No exceptions without ADR.",
        "domain": ["zira", "architecture", "principle", "coherence", "debt"],
    },
    {
        "name": "Sophie",
        "role": "Business Architecture",
        "incentives": "Strategy alignment, bedrijfsfuncties, diensten",
        "constraints": "No proposal without business value.",
        "domain": ["strategy", "business", "capability", "stakeholder"],
    },
    {
        "name": "Joris",
        "role": "Process Architecture",
        "incentives": "Care process impact, workflow changes, Wegiz compliance",
        "constraints": "Process changes must beclinically validated.",
        "domain": ["process", "workflow", "care", "wegiz"],
    },
    {
        "name": "Thomas",
        "role": "Application Architecture",
        "incentives": "Portfolio overlap, tech radar, build/buy/SaaS vendor evaluation",
        "constraints": "No new application without portfolio analysis.",
        "domain": [
            "application",
            "portfolio",
            "tech-radar",
            "vendor",
            "saas",
            "lifecycle",
        ],
    },
    {
        "name": "Lena",
        "role": "Integration Architecture",
        "incentives": "API standards, coupling risk, Cloverleaf routing, data flow integrity",
        "constraints": "All integrations must follow hospital API standards.",
        "domain": ["integration", "api", "cloverleaf", "hl7", "fhir", "coupling"],
    },
    {
        "name": "Jan",
        "role": "Technology & Infrastructure",
        "incentives": "Hosting, DR, RPO/RTO, operational readiness, monitoring",
        "constraints": "No system without DR plan if B ≥ 2.",
        "domain": ["infrastructure", "hosting", "dr", "rpo", "rto", "monitoring"],
    },
    {
        "name": "Aisha",
        "role": "Data & AI Architecture",
        "incentives": "Data classification, AVG/DPIA, data quality, EU AI Act, verwerkingsregister",
        "constraints": "No processing of personal data without DPIA assessment.",
        "domain": ["data", "privacy", "avg", "dpia", "ai", "classification"],
    },
    {
        "name": "Victor",
        "role": "Security Architecture (VETO)",
        "incentives": "STRIDE, zero trust, IAM, encryption, NEN 7510/7512, SBOM",
        "constraints": "VETO authority. Can block any proposal on security grounds.",
        "domain": ["security", "stride", "nen7510", "encryption", "iam", "zero-trust"],
    },
    {
        "name": "CISO",
        "role": "Strategic Security",
        "incentives": "Strategic security risk, SOC capacity, incident response",
        "constraints": "Escalates to Victor on technical findings.",
        "domain": ["security", "soc", "incident", "governance"],
    },
    {
        "name": "ISO-Officer",
        "role": "ISMS & Compliance",
        "incentives": "NEN 7510 ISMS, patch cycles, vulnerability management",
        "constraints": "No system without ISMS scope assessment.",
        "domain": ["isms", "nen7510", "patch", "vulnerability", "compliance"],
    },
    {
        "name": "Nadia",
        "role": "Risk & Compliance (ESCALATION)",
        "incentives": "NEN 7510/7512/7513, NIS2, AIVG 2022, vendor compliance, verwerkersovereenkomst",
        "constraints": "ESCALATION authority. Can upgrade board treatment.",
        "domain": ["risk", "compliance", "nen", "nis2", "aivg", "vendor"],
    },
    {
        "name": "FG-DPO",
        "role": "Privacy & Lawfulness (INDEPENDENT)",
        "incentives": "Verwerkingsgrondslag, DPIA, rechten betrokkenen, AVG Art 38(3)",
        "constraints": "INDEPENDENT. Cannot be overruled. Legal determination.",
        "domain": ["privacy", "avg", "dpia", "grondslag", "verwerking"],
    },
    {
        "name": "PO",
        "role": "Privacy by Design",
        "incentives": "Privacy by design, data minimization, verwerkingsregister, consent",
        "constraints": "Must consult FG-DPO on all personal data processing.",
        "domain": ["privacy", "design", "minimization", "consent"],
    },
    {
        "name": "Marco",
        "role": "Solution Architecture",
        "incentives": "Technical feasibility, NFRs, implementation complexity, migration",
        "constraints": "No proposal without feasibility assessment.",
        "domain": ["solution", "nfr", "implementation", "migration", "feasibility"],
    },
    {
        "name": "Daan",
        "role": "Information Architecture",
        "incentives": "Information ownership, WGBO retention, data lineage, records management",
        "constraints": "All data must have a designated owner.",
        "domain": ["information", "retention", "wgbo", "records", "lineage"],
    },
    {
        "name": "Ruben",
        "role": "Network Architecture",
        "incentives": "Network segmentation, firewall rules, VPN, DICOM networking",
        "constraints": "No flat network for clinical systems.",
        "domain": ["network", "firewall", "vpn", "segmentation", "dicom"],
    },
    {
        "name": "Femke",
        "role": "Portfolio Management",
        "incentives": "Roadmap alignment, capacity planning, sequencing, dependency management",
        "constraints": "No proposal without roadmap impact assessment.",
        "domain": ["portfolio", "roadmap", "capacity", "dependency", "sequencing"],
    },
    {
        "name": "Raven",
        "role": "Red Team (CHALLENGE)",
        "incentives": "Hidden assumptions, failure scenarios, groupthink detection, pre-mortem analysis",
        "constraints": "Advisory only. No veto, no escalation, but full access.",
        "domain": ["assumption", "failure", "groupthink", "pre-mortem", "challenge"],
    },
]


# ---------------------------------------------------------------------------
# Verwerkingsregister draft
# ---------------------------------------------------------------------------


def generate_verwerkingsregister_draft(
    proposal_name: str = "[voorstel]",
    processing_description: str = "",
    data_categories: list[str] | None = None,
    purpose: str = "",
    legal_basis: str = "",
    data_subjects: list[str] | None = None,
    recipients: list[str] | None = None,
    retention_period: str = "",
    datenschutz_guarantees: list[str] | None = None,
    persona_findings: list[dict] | None = None,
) -> dict:
    if persona_findings:
        data_categories = data_categories or _extract_data_categories(findings=persona_findings)
        data_subjects = data_subjects or _extract_data_subjects(findings=persona_findings)
        legal_basis = legal_basis or _extract_legal_basis(findings=persona_findings)
        recipients = recipients or _extract_recipients(findings=persona_findings)
        datenschutz_guarantees = datenschutz_guarantees or _extract_guarantees(
            findings=persona_findings
        )

    return {
        "proposal": proposal_name,
        "entry": {
            "verwerkingsactiviteit": processing_description
            or "[Beschrijving van de verwerkingsactiviteit]",
            "doel": purpose or "[Doel van de verwerking]",
            "grondslag": legal_basis or "[Verwerkingsgrondslag — AVG artikel 6 lid 1]",
            "categorie_betrokkenen": data_subjects or ["[Patiënten, Medewerkers, Bezoekers]"],
            "categorie_persoonsgegevens": data_categories
            or ["[BSN, naam, adres, medische gegevens]"],
            "ontvangers": recipients or ["[Ontvangers van de gegevens]"],
            "bewaartermijn": retention_period or "[Bewaartermijn]",
            "doorgifte_derde_landen": "[Nee / Ja — welke landen en welke waarborgen]",
            "datenschutz_garanties": datenschutz_guarantees
            or [
                "[Encryptie in transit en at rest, Toegangsbeperking op basis van rol, Audit logging per NEN 7513]"
            ],
        },
        "status": "CONCEPT — FG-bepaling vereist",
        "review_required": True,
        "reviewer": "FG-DPO",
        "disclaimer": (
            "Dit is een concept-verwerkingsregisterentry gegenereerd door Preflight. "
            "De FG/DPO beoordeelt de rechtmatigheid van de verwerking. "
            "Dit is geen vervanging van de FG-bepaling."
        ),
    }


def _extract_data_categories(findings: list[dict]) -> list[str]:
    categories = set()
    _PRIVACY_IDS = {"data", "fg-dpo", "privacy", "security"}
    for f in findings:
        pid = f.get("perspective_id", "")
        if pid in _PRIVACY_IDS:
            for finding in f.get("findings", []):
                if isinstance(finding, dict):
                    text = finding.get("finding", "")
                else:
                    text = str(finding)
                lower = text.lower()
                for cat, kws in [
                    ("BSN", ["bsn", "burgerservicenummer"]),
                    ("naam", ["naam", "naamgegevens"]),
                    ("adres", ["adres", "adresgegevens", "woonplaats"]),
                    (
                        "medische gegevens",
                        ["medisch", "zorggegevens", "patiëntgegevens", "patient data"],
                    ),
                    ("e-mail", ["e-mail", "emailadres"]),
                    ("telefoonnummer", ["telefoon", "telefoonnummer"]),
                    ("geboortedatum", ["geboortedatum", "geboorte"]),
                ]:
                    if any(kw in lower for kw in kws):
                        categories.add(cat)
    return sorted(categories) if categories else ["BSN", "naam", "medische gegevens"]


def _extract_data_subjects(findings: list[dict]) -> list[str]:
    subjects = set()
    _PRIVACY_IDS = {"data", "fg-dpo", "privacy"}
    for f in findings:
        pid = f.get("perspective_id", "")
        if pid in _PRIVACY_IDS:
            for finding in f.get("findings", []):
                text = (
                    finding.get("finding", "") if isinstance(finding, dict) else str(finding)
                ).lower()
                for subj, kws in [
                    ("Patiënten", ["patiënt", "patient", "zorg"]),
                    ("Medewerkers", ["medewerker", "werknemer", "personeel"]),
                    ("Bezoekers", ["bezoeker", "bezoek"]),
                    ("Verwijzers", ["verwijzer", "huisarts"]),
                ]:
                    if any(kw in text for kw in kws):
                        subjects.add(subj)
    return sorted(subjects) if subjects else ["Patiënten", "Medewerkers"]


def _extract_legal_basis(findings: list[dict]) -> str:
    _PRIVACY_IDS = {"fg-dpo", "privacy", "data"}
    for f in findings:
        pid = f.get("perspective_id", "")
        if pid in _PRIVACY_IDS:
            for finding in f.get("findings", []):
                text = (
                    finding.get("finding", "") if isinstance(finding, dict) else str(finding)
                ).lower()
                if any(kw in text for kw in ["grondslag", "avg", "gdpr", "artikel 6", "art. 6"]):
                    return f"[§P:{f.get('name', pid)}] — zie bevindingen voor grondslagbepaling"
    return "AVG Artikel 6 lid 1 sub e — verwerking noodzakelijk voor taak in algemeen belang"


def _extract_recipients(findings: list[dict]) -> list[str]:
    recipients = set()
    _RELEVANT_IDS = {"data", "fg-dpo", "privacy", "integration", "security"}
    for f in findings:
        pid = f.get("perspective_id", "")
        if pid in _RELEVANT_IDS:
            for finding in f.get("findings", []):
                text = (
                    finding.get("finding", "") if isinstance(finding, dict) else str(finding)
                ).lower()
                for rec, kws in [
                    ("Verzekeraars", ["verzekeraar", "zorgverzekeraar"]),
                    ("APV/GGD", ["ggd", "apv", "publieke gezondheid"]),
                    ("Leveranciers", ["leverancier", "vendor", "third party"]),
                    ("Verwijzers", ["verwijzer", "zienet", "huisarts"]),
                ]:
                    if any(kw in text for kw in kws):
                        recipients.add(rec)
    return sorted(recipients) if recipients else ["[Te bepalen door FG/DPO]"]


def _extract_guarantees(findings: list[dict]) -> list[str]:
    guarantees = set()
    _SECURITY_IDS = {"security", "ciso", "fg-dpo", "privacy"}
    for f in findings:
        pid = f.get("perspective_id", "")
        if pid in _SECURITY_IDS:
            for finding in f.get("findings", []):
                text = (
                    finding.get("finding", "") if isinstance(finding, dict) else str(finding)
                ).lower()
                if any(kw in text for kw in ["encrypt", "versleutel"]):
                    guarantees.add("Encryptie in transit en at rest")
                if any(kw in text for kw in ["toegang", "toegangsbeperk", "rbac", "role-based"]):
                    guarantees.add("Toegangsbeperking op basis van rol (RBAC)")
                if any(kw in text for kw in ["audit", "logging", "nen 7513", "7513"]):
                    guarantees.add("Audit logging per NEN 7513")
                if any(kw in text for kw in ["pseudonim", "gepseudonim"]):
                    guarantees.add("Pseudonimisatie waar mogelijk")
                if any(kw in text for kw in ["data minim", "dataminim"]):
                    guarantees.add("Dataminimalisatie")
    return (
        sorted(guarantees)
        if guarantees
        else [
            "Encryptie in transit en at rest",
            "Toegangsbeperking op basis van rol",
            "Audit logging per NEN 7513",
        ]
    )


# ---------------------------------------------------------------------------
# [ARCHITECT INPUT NEEDED] markers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Bilingual
# ---------------------------------------------------------------------------

NL_EN = {
    "Akkoord": {"nl": "Akkoord", "en": "Approve"},
    "Voorwaardelijk": {"nl": "Voorwaardelijk", "en": "Conditional"},
    "Bezorgd": {"nl": "Bezorgd", "en": "Concern"},
    "Blokkade": {"nl": "Blokkade", "en": "Block"},
    "N.v.t.": {"nl": "N.v.t.", "en": "N/A"},
    "Vetorecht": {"nl": "Vetorecht", "en": "Veto"},
    "Escalatie": {"nl": "Escalatie", "en": "Escalation"},
    "Onafhankelijk": {"nl": "Onafhankelijk", "en": "Independent"},
    "Concept": {"nl": "Concept", "en": "Draft"},
    "Goedkeuren": {"nl": "Goedkeuren", "en": "Approve"},
    "Goedkeuren met voorwaarden": {
        "nl": "Goedkeuren met voorwaarden",
        "en": "Approve with conditions",
    },
    "Afwijzen": {"nl": "Afwijzen", "en": "Reject"},
    "Uitstellen": {"nl": "Uitstellen", "en": "Defer"},
    "fast-track": {"nl": "fast-track", "en": "fast-track"},
    "standard-review": {"nl": "standaardbeoordeling", "en": "standard review"},
    "deep-review": {"nl": "diepgaande beoordeling", "en": "deep review"},
}


def t(term: str, lang: str = "nl") -> str:
    entry = NL_EN.get(term)
    return entry.get(lang, term) if entry else term


# ---------------------------------------------------------------------------
# Delta re-assessment
# ---------------------------------------------------------------------------

FIELD_PERSONA_MAP = {
    "integration": ["Lena", "Ruben", "Victor", "Jan"],
    "infrastructure": ["Jan", "Ruben", "Victor"],
    "data": ["Aisha", "FG-DPO", "PO"],
    "security": ["Victor", "CISO", "ISO-Officer"],
    "application": ["Thomas", "Lena", "Jan"],
    "vendor": ["Thomas", "Nadia", "Victor"],
    "clinical": ["CMIO", "FG-DPO", "PO"],
    "compliance": ["Nadia", "FG-DPO"],
    "budget": ["CIO"],
    "process": ["Joris", "CMIO"],
    "architecture": ["Marcus", "Sophie", "Femke"],
}


def determine_delta_reassessment(previous_assessment: dict, changes: dict) -> dict:
    re_assess = {"Marcus", "Raven"}
    reasons = [
        "Chief Architect always reassesses on changes",
        "Red Team reassesses on any change",
    ]

    for field in changes:
        affected = FIELD_PERSONA_MAP.get(field.lower(), [])
        for persona in affected:
            re_assess.add(persona)
        if affected:
            reasons.append(f"{field} changes affect: {', '.join(affected)}")

    if previous_assessment.get("ratings"):
        for pid, rating in previous_assessment["ratings"].items():
            if rating in ("block", "conditional"):
                name = _pid_to_name(pid)
                if name:
                    re_assess.add(name)

    all_personas = [_pid_to_name(pid) for pid in (previous_assessment.get("ratings") or {})]
    carry_forward = [p for p in all_personas if p and p not in re_assess]

    return {
        "re_assess": sorted(re_assess),
        "carry_forward": carry_forward,
        "reason": "; ".join(reasons),
    }


def _pid_to_name(pid: str) -> str | None:
    mapping = {
        "cio": "CIO",
        "cmio": "CMIO",
        "chief": "Marcus",
        "business": "Sophie",
        "process": "Joris",
        "application": "Thomas",
        "integration": "Lena",
        "infrastructure": "Jan",
        "data": "Aisha",
        "manufacturing": "Erik",
        "rnd": "Petra",
        "security": "Victor",
        "ciso": "CISO",
        "iso-officer": "ISO-Officer",
        "risk": "Nadia",
        "fg-dpo": "FG-DPO",
        "privacy": "PO",
        "solution": "Marco",
        "information": "Daan",
        "network": "Ruben",
        "portfolio": "Femke",
        "redteam": "Raven",
    }
    return mapping.get(pid)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
