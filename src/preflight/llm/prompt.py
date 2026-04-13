"""
Preflight prompt assembler — builds the batched assessment prompt.

This is the core product. If the prompt doesn't produce good structured
output, nothing else matters.

Design decisions:
- Prompt structure matches ARCHITECTURE.md Step 3 exactly
- Perspectives are injected as structured blocks, not free text
- Citation constraint is appended to every prompt
- Landscape context is quoted (input isolation), not injected as instructions
- Output format is specified with explicit delimiters for reliable parsing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


# ---------------------------------------------------------------------------
# Perspective definitions — condensed for batched evaluation
# ---------------------------------------------------------------------------

PERSPECTIVES = [
    {
        "id": "cio",
        "label": "CIO",
        "role": "Strategy & Investment",
        "focus": "IT strategy alignment, budget justification, TCO, shadow-IT risk, roadmap impact",
    },
    {
        "id": "cmio",
        "label": "CMIO",
        "role": "Clinical & Patient Safety",
        "focus": "Patient safety, clinical workflows, HL7/FHIR compliance, medical device classification (MDR/IVDR)",
    },
    {
        "id": "chief",
        "label": "Marcus — Chief Architect",
        "role": "Architecture Coherence",
        "focus": "ZiRA principle compliance, target architecture fit, architecture debt, capability map alignment",
    },
    {
        "id": "business",
        "label": "Sophie — Business Architecture",
        "role": "Strategy & Business Functions",
        "focus": "Strategy alignment, bedrijfsfunctie coverage, business value, stakeholders",
    },
    {
        "id": "process",
        "label": "Joris — Process Architecture",
        "role": "Process & Workflow",
        "focus": "Care process impact, workflow changes, handover risks, process compliance (Wegiz)",
    },
    {
        "id": "application",
        "label": "Thomas — Application Architecture",
        "role": "Portfolio & Technology",
        "focus": "Portfolio overlap, tech radar alignment, build/buy/SaaS, vendor viability, lifecycle",
    },
    {
        "id": "integration",
        "label": "Lena — Integration Architecture",
        "role": "Integration & Data Flow",
        "focus": "API standards, coupling risk, Cloverleaf routing, HL7/FHIR message specs, data flow integrity",
    },
    {
        "id": "infrastructure",
        "label": "Jan — Technology & Infrastructure",
        "role": "Hosting & Operations",
        "focus": "Hosting model, DR/RPO/RTO, capacity impact, operational readiness, monitoring",
    },
    {
        "id": "data",
        "label": "Aisha — Data & AI Architecture",
        "role": "Data & Privacy",
        "focus": "Data classification, AVG/GDPR, DPIA triggers, EU AI Act, data quality, verwerkingsregister",
    },
    {
        "id": "security",
        "label": "Victor — Security Architecture",
        "role": "Security (VETO AUTHORITY)",
        "focus": "STRIDE threat model, zero trust, IAM, encryption, NEN 7510/7512, SBOM — CAN VETO",
    },
    {
        "id": "ciso",
        "label": "CISO",
        "role": "Strategic Security",
        "focus": "Strategic security risk, SOC capacity, incident response, security governance",
    },
    {
        "id": "iso-officer",
        "label": "ISO-Officer",
        "role": "ISMS & Compliance",
        "focus": "NEN 7510 ISMS scope, patch cycles, vulnerability management, monitoring compliance",
    },
    {
        "id": "risk",
        "label": "Nadia — Risk & Compliance",
        "role": "Regulatory & Risk (ESCALATION AUTHORITY)",
        "focus": "NEN 7510/7512/7513, NIS2, AIVG 2022, vendor compliance, verwerkersovereenkomst — CAN ESCALATE",
    },
    {
        "id": "fg-dpo",
        "label": "FG/DPO",
        "role": "Privacy & Lawfulness (INDEPENDENT AUTHORITY)",
        "focus": "Verwerkingsgrondslag, DPIA, rechten betrokkenen, AVG Art 38(3) — CANNOT BE OVERRULEN",
    },
    {
        "id": "privacy",
        "label": "PO — Privacy Officer",
        "role": "Privacy by Design",
        "focus": "Privacy by design, data minimization, verwerkingsregister, consent management",
    },
    {
        "id": "solution",
        "label": "Marco — Solution Architecture",
        "role": "Implementation Feasibility",
        "focus": "Technical feasibility, NFRs, implementation complexity, migration approach",
    },
    {
        "id": "information",
        "label": "Daan — Information Architecture",
        "role": "Information & Records",
        "focus": "Information ownership, WGBO retention, data lineage, records management",
    },
    {
        "id": "network",
        "label": "Ruben — Network Architecture",
        "role": "Network & Connectivity",
        "focus": "Network segmentation, firewall rules, VPN, DICOM networking, Cloverleaf connectivity",
    },
    {
        "id": "portfolio",
        "label": "Femke — Portfolio Management",
        "role": "Portfolio & Roadmap",
        "focus": "Roadmap alignment, capacity planning, sequencing, dependency management",
    },
    {
        "id": "manufacturing",
        "label": "Erik — Manufacturing & OT",
        "role": "Operational Technology",
        "focus": "SCADA, PLC, manufacturing execution, OT security boundaries, Purdue model, industrial protocols",
    },
    {
        "id": "rnd",
        "label": "Petra — R&D & Engineering",
        "role": "Research & Development",
        "focus": "Innovation pipeline, research data governance, IP protection, export control, clinical trials",
    },
]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

CITATION_CONSTRAINT = """
CITATION RULES — YOU MUST FOLLOW THESE:
1. Every factual claim MUST cite its source.
2. Use [§P:PersonaName] for claims from your own expertise as this persona.
3. Use [§K:source-id] for claims from the retrieved context below.
4. If you cannot verify a claim from available sources, write "[VERIFY]" after it.
5. Do NOT fabricate source IDs. Only cite sources present in the context.
6. Do NOT make claims without citations. Uncited claims will be flagged.
"""

ACCOUNTABILITY = """
IMPORTANT: You are generating a DRAFT assessment. A real {role} will review your output.
Do not cite regulatory articles or standards unless they appear in the retrieved context below.
If you are unsure whether a specific regulation applies, say so — do not fabricate references.
"""

OUTPUT_FORMAT_FAST = """
Output format — follow this EXACTLY:

[PERSPECTIVE_RATINGS]
{id1}:{rating1} {id2}:{rating2} {id3}:{rating3} ...
[/PERSPECTIVE_RATINGS]

[PERSPECTIVE_FINDINGS]
{id1}: {one sentence reason for non-approve rating, or "No concerns" if approve}
{id2}: {one sentence reason}
...
[/PERSPECTIVE_FINDINGS]

[PERSPECTIVE_CONDITIONS]
{id1}: {comma-separated conditions for approval, or "None" if approve}
{id2}: {comma-separated conditions}
...
[/PERSPECTIVE_CONDITIONS]

Rating options: approve, conditional, concern, block, na
- approve: No concerns from this perspective
- conditional: Approve IF specific conditions are met
- concern: Significant risk flagged but not blocking
- block: This proposal must not proceed without fundamental change
- na: This perspective is not relevant to this proposal
"""


def build_fast_assessment_prompt(
    request_description: str,
    selected_perspective_ids: Sequence[str],
    landscape_context: str | None = None,
    retrieved_context: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Build the batched assessment prompt for fast mode.

    Returns (system_prompt, user_prompt).
    """
    selected = [p for p in PERSPECTIVES if p["id"] in selected_perspective_ids]
    if not selected:
        selected = PERSPECTIVES[:10]  # fallback to first 10

    system = _build_system_prompt(selected)
    user = _build_user_prompt(
        request_description, selected, landscape_context, retrieved_context
    )

    return system, user


def _build_system_prompt(selected: list[dict]) -> str:
    perspectives_block = "\n".join(
        f"- **{p['id']}** ({p['label']} — {p['role']}): {p['focus']}" for p in selected
    )

    return f"""You are simulating the Enterprise Architecture Board of a Dutch hospital.

You will evaluate a proposal from MULTIPLE perspectives simultaneously.
Each perspective represents a different board member with specific concerns.

## Perspectives
{perspectives_block}

## Authority Types
- VETO (Victor — Security): Can block the proposal. Conditions become mandatory.
- ESCALATION (Nadia — Risk): Can upgrade board treatment to deep review.
- INDEPENDENT (FG/DPO — Privacy): Cannot be overruled. Legal determination.

{CITATION_CONSTRAINT}

{OUTPUT_FORMAT_FAST}"""


def _build_user_prompt(
    request_description: str,
    selected: list[dict],
    landscape_context: str | None,
    retrieved_context: dict[str, str] | None,
) -> str:
    parts = [f"## Proposal\n\n{request_description}\n"]

    if landscape_context:
        parts.append(f"""## Landscape Context
The following context was queried from the hospital's ArchiMate model, TOPdesk CMDB, and LeanIX portfolio:

---
{landscape_context}
---\n""")

    if retrieved_context:
        context_block = "\n".join(
            f"### Context for {pid}\n{ctx}\n"
            for pid, ctx in retrieved_context.items()
            if pid in [p["id"] for p in selected]
        )
        if context_block:
            parts.append(
                f"## Retrieved Knowledge (cite these as [§K:source-id])\n\n{context_block}"
            )

    parts.append(
        "Evaluate this proposal from EACH perspective listed above. Use the output format specified."
    )

    return "\n".join(parts)


def build_deep_assessment_prompt(
    persona: dict,
    request_description: str,
    landscape_context: str | None = None,
    retrieved_context: str | None = None,
    interaction_round: dict | None = None,
) -> tuple[str, str]:
    """Build a single-persona deep assessment prompt.

    Returns (system_prompt, user_prompt).
    """
    name = persona["label"].split(" — ")[0].strip()
    role = persona["role"]
    focus = persona["focus"]

    system = f"""You are simulating {name}, {role} on the Enterprise Architecture Board of a Dutch hospital.

## What You Care About
{focus}

{CITATION_CONSTRAINT}

{ACCOUNTABILITY.format(role=role)}

You must rate this proposal: approve / conditional / concern / block

For conditional/concern/block, state:
- Your specific finding (grounded in the retrieved context, cite sources)
- Your strongest objection — what could kill it from your perspective
- Your hidden concern — what you're thinking but won't say in the meeting
- Your conditions for approval (actionable, measurable)
- What you would need to see to change your rating

Output format:
[MY_RATING]
one of: approve, conditional, concern, block
[/MY_RATING]

[FINDINGS]
- finding 1
- finding 2
[/FINDINGS]

[STRONGEST_OBJECTION]
your strongest objection
[/STRONGEST_OBJECTION]

[HIDDEN_CONCERN]
what you're thinking but won't say
[/HIDDEN_CONCERN]

[CONDITIONS]
- condition 1
- condition 2
[/CONDITIONS]

[RATING_CHANGE_TRIGGER]
what would make you change your rating
[/RATING_CHANGE_TRIGGER]"""

    user_parts = [f"## Proposal\n\n{request_description}\n"]

    if landscape_context:
        user_parts.append(f"## Landscape Context\n---\n{landscape_context}\n---\n")

    if retrieved_context:
        user_parts.append(f"## Retrieved Knowledge\n---\n{retrieved_context}\n---\n")

    if interaction_round:
        other_reactions = interaction_round.get("reactions", "")
        if other_reactions:
            user_parts.append(
                f"## Other Board Members' Reactions\n{other_reactions}\n\nRespond to any points that affect your assessment."
            )

    user_parts.append(
        "Provide your assessment using the output format specified above."
    )

    return system, "\n".join(user_parts)


PERSONA_VERSION = "1.0.0"


def persona_hash() -> str:
    import hashlib

    payload = "|".join(f"{p['id']}:{p['role']}:{p['focus']}" for p in PERSPECTIVES)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
