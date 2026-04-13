"""
Authority enforcement — ensures authority persona overrides are applied correctly.

The EA council has five authority types. This module enforces them:
- VETO (Victor — Security): Can block the proposal. If triggered, no override possible.
- ESCALATION (Nadia — Risk): Upgrades treatment. Overrides downgrade attempts.
- INDEPENDENT (FG/DPO — Privacy): Cannot be overruled. Legal determination stands.
- PATIENT_SAFETY (CMIO): Cannot be fast-tracked. Clinical systems always get this.
- CHALLENGE (Raven): Advisory. Does not override but flags for architect review.

Thinking applied:
  First principles: Authority actions are NOT advisory opinions. They are
  structural constraints on the assessment. VETO means the proposal is blocked.
  INDEPENDENT means the FG/DPO determination cannot be challenged by other personas.
  These must be enforced AFTER all interaction rounds, not just detected.
  Second order: If Victor VETOes but Sophie says approve, Sophie's approve is
  not wrong — it's her perspective. But the OVERALL assessment must reflect
  that a VETO exists. Authority enforcement operates on the aggregate, not the
  individual persona finding.
  Inversion: What if authority enforcement is too aggressive? A false VETO
  (LLM hallucinated a security block) would incorrectly kill a proposal.
  Solution: All authority actions are DRAFTS requiring human sign-off. The
  enforcement here marks the assessment status and adds mandatory conditions,
  but doesn't prevent the architect from overridding in review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuthorityEnforcementResult:
    overall_status: str = "OPEN"
    blocked_by: list[str] = field(default_factory=list)
    escalated: bool = False
    independent_determinations: list[str] = field(default_factory=list)
    patient_safety_floor: bool = False
    challenge_flags: list[str] = field(default_factory=list)
    mandatory_conditions: list[str] = field(default_factory=list)
    treatment_override: str | None = None
    details: list[str] = field(default_factory=list)


AUTHORITY_SEVERITY = {
    "VETO": 4,
    "INDEPENDENT": 3,
    "ESCALATION": 2,
    "PATIENT_SAFETY": 2,
    "CHALLENGE": 1,
}

STATUS_PRECEDENCE = {
    "BLOCKED": 0,
    "ESCALATED": 1,
    "CONDITIONAL_WITH_FLOOR": 2,
    "CONDITIONAL": 3,
    "CHALLENGED": 4,
    "OPEN": 5,
}


def enforce_authority(
    persona_findings: list[dict],
    authority_actions: list[dict],
    current_treatment: str = "standard-review",
    request_type: str = "",
) -> AuthorityEnforcementResult:
    """Enforce authority persona overrides on the assessment.

    Called AFTER all interaction rounds and AFTER process_authority_actions().
    Does NOT modify persona findings — it marks the overall assessment status.

    Returns AuthorityEnforcementResult with:
    - overall_status: BLOCKED, ESCALATED, CONDITIONAL, CHALLENGED, or OPEN
    - mandatory conditions from triggered authorities
    - treatment override if escalation is active
    """
    result = AuthorityEnforcementResult()

    triggered_actions = [a for a in authority_actions if a.get("triggered")]

    if not triggered_actions:
        result.overall_status = "OPEN"
        result.details.append("No authority actions triggered — assessment is open")
        return result

    for action in triggered_actions:
        auth_type = action.get("type", "")
        persona = action.get("persona", "")
        findings = action.get("findings", [])
        conditions = action.get("conditions", [])

        if auth_type == "VETO":
            result.overall_status = "BLOCKED"
            result.blocked_by.append(persona)
            for f in findings[:5]:
                result.mandatory_conditions.append(f"[VETO {persona}] {f}")
            for c in conditions[:5]:
                result.mandatory_conditions.append(f"[VETO-CONDITION {persona}] {c}")
            result.details.append(
                f"VETO by {persona} — proposal is blocked. "
                "All VETO conditions are mandatory. "
                "Only human sign-off can override."
            )

        elif auth_type == "INDEPENDENT":
            if (
                STATUS_PRECEDENCE.get(result.overall_status, 5)
                > STATUS_PRECEDENCE["CONDITIONAL_WITH_FLOOR"]
            ):
                result.overall_status = "CONDITIONAL_WITH_FLOOR"
            result.independent_determinations.append(persona)
            for c in conditions[:5]:
                result.mandatory_conditions.append(f"[INDEPENDENT {persona}] {c}")
            result.details.append(
                f"INDEPENDENT determination by {persona} — cannot be overruled by other personas. "
                "These conditions are legally binding."
            )

        elif auth_type == "ESCALATION":
            result.escalated = True
            if result.overall_status not in ("BLOCKED",):
                result.overall_status = "ESCALATED"
            result.treatment_override = "deep-review"
            result.details.append(
                f"ESCALATION by {persona} — treatment upgraded to deep-review. "
                "Board must review with full authority present."
            )

        elif auth_type == "PATIENT_SAFETY":
            result.patient_safety_floor = True
            if result.overall_status not in ("BLOCKED", "ESCALATED", "CONDITIONAL_WITH_FLOOR"):
                result.overall_status = "CONDITIONAL_WITH_FLOOR"
            for c in conditions[:5]:
                result.mandatory_conditions.append(f"[PATIENT_SAFETY {persona}] {c}")
            result.details.append(
                f"PATIENT_SAFETY floor by {persona} — cannot be fast-tracked. "
                "Clinical safety conditions are mandatory."
            )

        elif auth_type == "CHALLENGE":
            result.challenge_flags.append(persona)
            if result.overall_status == "OPEN":
                result.overall_status = "CHALLENGED"
            result.details.append(f"CHALLENGE by {persona} — advisory flag. Architect must review.")

    if result.treatment_override and result.treatment_override != current_treatment:
        result.details.append(
            f"Treatment overridden: {current_treatment} → {result.treatment_override}"
        )

    return result


def apply_authority_to_findings(
    persona_findings: list[dict],
    enforcement: AuthorityEnforcementResult,
) -> list[dict]:
    """Mark persona findings that conflict with authority enforcement.

    Adds an 'authority_conflict' field to findings that rate 'approve'
    when a VETO or INDEPENDENT authority has been triggered.

    Does NOT change ratings — that's the architect's job.
    """
    if enforcement.overall_status not in ("BLOCKED", "CONDITIONAL_WITH_FLOOR", "ESCALATED"):
        return persona_findings

    conflict_types = set()
    if enforcement.blocked_by:
        conflict_types.add("VETO")
    if enforcement.independent_determinations:
        conflict_types.add("INDEPENDENT")

    if not conflict_types:
        return persona_findings

    for pf in persona_findings:
        rating = pf.get("rating", "na")
        revised = pf.get("revised_rating")
        effective_rating = revised or rating
        if effective_rating == "approve":
            pf["authority_conflict"] = (
                f"Rates 'approve' but {', '.join(conflict_types)} authority is active. "
                "This perspective should be noted but does not override the authority action."
            )

    return persona_findings


def generate_authority_summary(enforcement: AuthorityEnforcementResult) -> str:
    """Generate a human-readable summary of authority enforcement for the PSA."""
    lines = []

    if enforcement.overall_status == "BLOCKED":
        lines.append("## Bevoegdheidsacties — VETO ACTIEF")
        lines.append("")
        lines.append(
            "Dit voorstel is **geblokkeerd** door een VETO-bevoegdheid. "
            "Alleen handmatige goedkeuring door de bevoegde persoon kan dit opheffen."
        )
    elif enforcement.overall_status == "ESCALATED":
        lines.append("## Bevoegdheidsacties — ESCALATIE")
        lines.append("")
        lines.append(
            "Dit voorstel is **geëscaleerd** naar deep-review. "
            "De volledige raad moet aanwezig zijn bij de beoordeling."
        )
    elif enforcement.overall_status == "CONDITIONAL_WITH_FLOOR":
        lines.append("## Bevoegdheidsacties — Onafhankelijke Bepaling / Patiëntveiligheid")
        lines.append("")
        lines.append(
            "Dit voorstel heeft een **onafhankelijke bepaling** of **patiëntveiligheidsvloer**. "
            "Versnelling (fast-track) is niet mogelijk."
        )
    elif enforcement.overall_status == "CHALLENGED":
        lines.append("## Bevoegdheidsacties — Auditieve Achtervang")
        lines.append("")
        lines.append(
            "Dit voorstel is **aangevochten** door de Red Team. De architect moet hierop reageren."
        )
    else:
        lines.append("## Bevoegdheidsacties — Geen Bevoegdheid Geactiveerd")
        lines.append("")
        lines.append("Geen VETO, escalatie, of onafhankelijke bepaling geactiveerd.")
        return "\n".join(lines)

    lines.append("")
    if enforcement.blocked_by:
        lines.append(f"- **VETO:** {', '.join(enforcement.blocked_by)}")
    if enforcement.escalated:
        lines.append("- **ESCALATIE:** Behandeling opgewaardeerd naar deep-review")
    if enforcement.independent_determinations:
        lines.append(
            f"- **ONAFHANKELIJK:** {', '.join(enforcement.independent_determinations)} — kan niet worden overruled"
        )
    if enforcement.patient_safety_floor:
        lines.append("- **PATIËNTVEILIGHEID:** Fast-track niet mogelijk voor klinische systemen")

    if enforcement.mandatory_conditions:
        lines.append("")
        lines.append("### Verplichte Voorwaarden")
        lines.append("")
        for mc in enforcement.mandatory_conditions:
            lines.append(f"- {mc}")

    lines.append("")
    lines.append(
        "> **Let op:** Alle bevoegdheidsacties zijn CONCEPT. De bevoegde persoon moet bevestigen voordat deze van kracht worden."
    )

    return "\n".join(lines)
