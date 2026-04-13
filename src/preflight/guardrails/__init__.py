"""
Preflight guardrails — safety boundaries for the LLM-assisted assessment pipeline.

NeMo Guardrails integration with pure-Python fallback. Every assessment passes
through the GuardrailEngine before output delivery. Rail enforcement prevents:
- Hallucinated regulatory citations
- Bypassing mandatory authority review (VETO, ESCALATION, INDEPENDENT, PATIENT_SAFETY)
- Fast-tracking clinical-system requests
- Skipping DPIA/FG-DPO review for patient data
- Malformed output products

Design decisions:
- nemoguardrails is OPTIONAL — the engine falls back to pure-Python validation
- Rails work with both fast mode (batched PERSPECTIVES) and deep mode (simulatePanel)
- Each rail returns GuardrailResult with pass/fail/escalate action
- Authority persona outputs are ALWAYS drafts requiring human sign-off
- Hard triage floors: clinical-system → no fast-track, patient-data → FG-DPO mandatory
"""

from preflight.guardrails.config import GuardrailConfig
from preflight.guardrails.engine import GuardrailEngine
from preflight.guardrails.rails import (
    AuthorityRail,
    ClinicalSystemRail,
    CitationRail,
    GuardrailAction,
    GuardrailResult,
    OutputValidationRail,
    PatientDataRail,
)

__all__ = [
    "GuardrailConfig",
    "GuardrailEngine",
    "GuardrailResult",
    "GuardrailAction",
    "CitationRail",
    "AuthorityRail",
    "ClinicalSystemRail",
    "PatientDataRail",
    "OutputValidationRail",
]
