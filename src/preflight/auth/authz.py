"""
Preflight AuthZ — RBAC + ABAC content-driven authorization.

FIRST PRINCIPLES:
  1. RBAC answers "can this role DO this action?" — static, predictable
  2. ABAC answers "can this role SEE this content?" — dynamic, driven by classification
  3. ABAC triggers MID-ASSESSMENT, not before. Aisha classifies data as patient-data
     AFTER Step 3 runs. Access rules must spread AFTER classification.
  4. The two layers are INDEPENDENT. RBAC deny → hard no. ABAC deny → can't see, but action completes.

INVERSION: What makes AuthZ fail?
  - RBAC too rigid → board can't override persona recommendations
    → lead-architect CAN override, with documented rationale
  - ABAC too loose → anyone sees patient data
    → patient-data classification auto-restricts to clinical-access roles
  - Classification is wrong → patient data visible to non-clinical
    → "pending-classification" state: only architect+ can see until classified
  - Authority persona (Victor) needs to see patient data to assess
    → authority check happens BEFORE ABAC check
  - FG-DPO determination must be visible to compliance-officer
    → Nadia's ESCALATION auto-grants compliance-officer + fg-dpo access
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from preflight.auth.authn import AuthUser, RoleMapper, ROLE_HIERARCHY


class Action(str, Enum):
    SUBMIT_REQUEST = "submit_request"
    RUN_ASSESSMENT = "run_assessment"
    VIEW_ASSESSMENT = "view_assessment"
    VIEW_ALL_ASSESSMENTS = "view_all_assessments"
    OVERRIDE_FINDING = "override_finding"
    APPROVE_FAST_TRACK = "approve_fast_track"
    SIGN_OFF_AUTHORITY = "sign_off_authority"
    BOARD_DECISION = "board_decision"
    MANAGE_PERSONAS = "manage_personas"
    MANAGE_KNOWLEDGE = "manage_knowledge"
    EXPORT_AUDIT = "export_audit"
    ADMIN_CONFIG = "admin_config"
    VIEW_DASHBOARD = "view_dashboard"
    UPLOAD_DOCUMENTS = "upload_documents"
    VIEW_CONDITIONS = "view_conditions"
    RESOLVE_CONDITION = "resolve_condition"


class Classification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PATIENT_DATA = "patient-data"
    EXPORT_CONTROLLED = "export-controlled"
    PENDING = "pending-classification"


RBAC_POLICY: dict[str, set[Action]] = {
    "requestor": {
        Action.SUBMIT_REQUEST,
        Action.VIEW_ASSESSMENT,
        Action.VIEW_CONDITIONS,
    },
    "architect": {
        Action.SUBMIT_REQUEST,
        Action.RUN_ASSESSMENT,
        Action.VIEW_ASSESSMENT,
        Action.VIEW_ALL_ASSESSMENTS,
        Action.UPLOAD_DOCUMENTS,
        Action.VIEW_CONDITIONS,
        Action.RESOLVE_CONDITION,
        Action.VIEW_DASHBOARD,
    },
    "lead-architect": {
        Action.SUBMIT_REQUEST,
        Action.RUN_ASSESSMENT,
        Action.VIEW_ASSESSMENT,
        Action.VIEW_ALL_ASSESSMENTS,
        Action.UPLOAD_DOCUMENTS,
        Action.OVERRIDE_FINDING,
        Action.APPROVE_FAST_TRACK,
        Action.VIEW_CONDITIONS,
        Action.RESOLVE_CONDITION,
        Action.VIEW_DASHBOARD,
    },
    "board-member": {
        Action.VIEW_ASSESSMENT,
        Action.VIEW_ALL_ASSESSMENTS,
        Action.VIEW_CONDITIONS,
        Action.VIEW_DASHBOARD,
    },
    "board-chair": {
        Action.VIEW_ASSESSMENT,
        Action.VIEW_ALL_ASSESSMENTS,
        Action.BOARD_DECISION,
        Action.SIGN_OFF_AUTHORITY,
        Action.VIEW_CONDITIONS,
        Action.RESOLVE_CONDITION,
        Action.VIEW_DASHBOARD,
    },
    "chief-architect": {
        Action.SUBMIT_REQUEST,
        Action.RUN_ASSESSMENT,
        Action.VIEW_ASSESSMENT,
        Action.VIEW_ALL_ASSESSMENTS,
        Action.OVERRIDE_FINDING,
        Action.APPROVE_FAST_TRACK,
        Action.SIGN_OFF_AUTHORITY,
        Action.MANAGE_PERSONAS,
        Action.MANAGE_KNOWLEDGE,
        Action.VIEW_CONDITIONS,
        Action.RESOLVE_CONDITION,
        Action.VIEW_DASHBOARD,
    },
    "cio": {
        Action.VIEW_ALL_ASSESSMENTS,
        Action.VIEW_DASHBOARD,
    },
    "compliance-officer": {
        Action.VIEW_ALL_ASSESSMENTS,
        Action.EXPORT_AUDIT,
        Action.VIEW_DASHBOARD,
    },
    "fg-dpo": {
        Action.VIEW_ALL_ASSESSMENTS,
        Action.SIGN_OFF_AUTHORITY,
        Action.VIEW_DASHBOARD,
    },
    "admin": {
        Action.ADMIN_CONFIG,
        Action.MANAGE_KNOWLEDGE,
    },
}

for role, actions in list(RBAC_POLICY.items()):
    inherited = set()
    for parent_role in ROLE_HIERARCHY.get(role, set()):
        if parent_role != role and parent_role in RBAC_POLICY:
            inherited.update(RBAC_POLICY[parent_role])
    RBAC_POLICY[role] = actions | inherited

ABAC_POLICY: dict[str, dict] = {
    "patient-data-restriction": {
        "trigger": "Aisha classifies data as bijzondere persoonsgegevens",
        "condition": "classification == PATIENT_DATA",
        "effect": "restrict_to",
        "allowed_roles": {
            "architect",
            "lead-architect",
            "chief-architect",
            "compliance-officer",
            "fg-dpo",
        },
        "require_clearance": "patient-data",
        "require_clinical_access": True,
    },
    "export-control-restriction": {
        "trigger": "Petra flags export-controlled",
        "condition": "classification == EXPORT_CONTROLLED",
        "effect": "restrict_to",
        "allowed_roles": {"architect", "lead-architect", "chief-architect"},
        "require_clearance": "export-clearance",
    },
    "vendor-confidential": {
        "trigger": "Marked at intake",
        "condition": "classification == CONFIDENTIAL and source == vendor_doc",
        "effect": "restrict_to",
        "allowed_roles": {
            "architect",
            "lead-architect",
            "chief-architect",
            "board-member",
            "board-chair",
        },
    },
    "board-only-findings": {
        "trigger": "Raven (Red Team) findings in Step 4",
        "condition": "finding_source == 'redteam' and step == 4",
        "effect": "restrict_to",
        "allowed_roles": {"board-member", "board-chair", "chief-architect"},
    },
    "compliance-escalation": {
        "trigger": "Nadia triggers ESCALATION",
        "condition": "authority_action_type == 'ESCALATION'",
        "effect": "auto_grant",
        "grant_to": {"compliance-officer", "fg-dpo"},
        "duration": " until assessment is DECIDED",
    },
    "pending-classification": {
        "trigger": "Assessment not yet classified by Aisha",
        "condition": "classification == PENDING",
        "effect": "restrict_to",
        "allowed_roles": {"architect", "lead-architect", "chief-architect"},
    },
}


@dataclass
class AuthZDecision:
    allowed: bool
    reason: str = ""
    missing_roles: list[str] = field(default_factory=list)
    missing_clearance: str = ""
    classification_applied: str = ""


class Authorizer:
    """Combined RBAC + ABAC authorization engine.

    RBAC is checked first (deny → hard no).
    ABAC is checked second (deny → can't see content, but action may complete).
    """

    def __init__(self):
        self._role_mapper = RoleMapper()

    def check_rbac(self, user: AuthUser, action: Action) -> AuthZDecision:
        """Check if user's role permits this action."""
        allowed_actions = RBAC_POLICY.get(user.role, set())
        if action in allowed_actions:
            return AuthZDecision(
                allowed=True, reason=f"RBAC: {user.role} can {action.value}"
            )

        return AuthZDecision(
            allowed=False,
            reason=f"RBAC: {user.role} cannot {action.value}",
            missing_roles=self._find_roles_with_action(action),
        )

    def check_abac(
        self,
        user: AuthUser,
        classification: Classification,
        finding_source: str = "",
        authority_action_type: str = "",
    ) -> AuthZDecision:
        """Check content-driven access policies.

        SECOND ORDER: ABAC classification happens mid-assessment.
        A patient-data classification by Aisha means access must be
        re-evaluated AFTER Step 3, not before. This method is called
        at read time, not at write time.
        """
        if classification == Classification.PUBLIC:
            return AuthZDecision(allowed=True, reason="Public content")

        if classification == Classification.INTERNAL:
            if user.is_authenticated:
                return AuthZDecision(
                    allowed=True, reason="Internal content, authenticated user"
                )
            return AuthZDecision(
                allowed=False, reason="Internal content requires authentication"
            )

        if classification == Classification.PENDING:
            if user.role in ("architect", "lead-architect", "chief-architect"):
                return AuthZDecision(
                    allowed=True,
                    reason="Pending classification, architect-level access",
                    classification_applied="pending-classification",
                )
            return AuthZDecision(
                allowed=False,
                reason="Content pending classification, only architect-level access",
                classification_applied="pending-classification",
            )

        if classification == Classification.PATIENT_DATA:
            if not user.clinical_access:
                return AuthZDecision(
                    allowed=False,
                    reason="Patient data requires clinical-access clearance",
                    classification_applied="patient-data-restriction",
                )
            if user.clearance_level not in (
                "patient-data",
                "confidential",
                "export-clearance",
            ):
                return AuthZDecision(
                    allowed=False,
                    reason="Patient data requires patient-data clearance level",
                    missing_clearance="patient-data",
                    classification_applied="patient-data-restriction",
                )
            return AuthZDecision(
                allowed=True,
                reason="Patient data access granted",
                classification_applied="patient-data-restriction",
            )

        if classification == Classification.EXPORT_CONTROLLED:
            if user.clearance_level != "export-clearance":
                return AuthZDecision(
                    allowed=False,
                    reason="Export-controlled content requires export-clearance",
                    missing_clearance="export-clearance",
                    classification_applied="export-control-restriction",
                )
            return AuthZDecision(
                allowed=True,
                reason="Export-controlled access granted",
                classification_applied="export-control-restriction",
            )

        if classification == Classification.CONFIDENTIAL:
            if (
                finding_source == "redteam"
                and not user.is_board
                and user.role != "chief-architect"
            ):
                return AuthZDecision(
                    allowed=False,
                    reason="Red Team findings are board + chief-architect only",
                    classification_applied="board-only-findings",
                )
            if user.role in (
                "architect",
                "lead-architect",
                "chief-architect",
                "board-member",
                "board-chair",
            ):
                return AuthZDecision(
                    allowed=True,
                    reason="Confidential content, authorized role",
                )
            return AuthZDecision(
                allowed=False,
                reason="Confidential content requires architect or board role",
            )

        return AuthZDecision(allowed=False, reason="Unknown classification")

    def check_escalation_access(self, user: AuthUser, authority_type: str) -> bool:
        """INVERSION: What if Nadia escalates but compliance can't see it?

        AUTHORITY ESCALATION auto-grants access to compliance-officer and fg-dpo.
        This is by design — an escalation without visibility is useless.
        """
        if authority_type == "ESCALATION":
            return user.role in (
                "compliance-officer",
                "fg-dpo",
                "chief-architect",
                "lead-architect",
                "board-chair",
            )
        if authority_type == "VETO":
            return user.role in ("chief-architect", "security") or user.is_architect
        if authority_type == "INDEPENDENT":
            return user.role in ("fg-dpo", "chief-architect")
        return False

    def _find_roles_with_action(self, action: Action) -> list[str]:
        """Find roles that have this action — for helpful deny messages."""
        return [role for role, actions in RBAC_POLICY.items() if action in actions]


def classify_assessment(
    persona_findings: list[dict],
    authority_actions: list[dict],
    vendor_confidential: bool = False,
) -> Classification:
    """Determine the ABAC classification for an assessment.

    Called AFTER Step 3 (assessment) and Step 4 (authority challenge).
    The classification drives access control for reading the assessment.

    FIRST PRINCIPLE: Classification is driven by data, not by who submitted it.
    INVERSION: What if classification is too strict? → Architects can always see.
    What if it's too loose? → Pending-classification is the safe default.
    """
    has_patient_data = False
    has_export_control = False
    has_redteam_findings = False
    has_escalation = False

    for finding in persona_findings:
        pid = finding.get("perspective_id", "")
        data_tags = finding.get("data_tags", [])
        if not isinstance(data_tags, list):
            data_tags = []
        rating = finding.get("rating", "")

        if pid == "data" and "patient-data" in [t.lower() for t in data_tags]:
            has_patient_data = True
        if pid == "rnd" and (
            "export-controlled" in [t.lower() for t in data_tags] or rating == "block"
        ):
            has_export_control = True
        if pid == "redteam":
            has_redteam_findings = True

    for action in authority_actions:
        atype = action.get("action_type", "")
        if atype == "ESCALATION":
            has_escalation = True

    if has_patient_data:
        return Classification.PATIENT_DATA
    if has_export_control:
        return Classification.EXPORT_CONTROLLED
    if vendor_confidential or has_redteam_findings:
        return Classification.CONFIDENTIAL

    return Classification.INTERNAL
