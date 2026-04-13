"""
Tests for authority enforcement — VETO, ESCALATION, INDEPENDENT, PATIENT_SAFETY, CHALLENGE.
"""

import pytest

from preflight.pipeline.authority import (
    AuthorityEnforcementResult,
    enforce_authority,
    apply_authority_to_findings,
    generate_authority_summary,
)


def _make_action(auth_type: str, persona: str, triggered: bool = True) -> dict:
    return {
        "type": auth_type,
        "persona": persona,
        "triggered": triggered,
        "findings": [f"{auth_type} finding from {persona}"],
        "conditions": [f"{auth_type} condition from {persona}"],
    }


def _make_finding(pid: str, rating: str) -> dict:
    return {"perspective_id": pid, "name": pid, "rating": rating, "findings": [], "conditions": []}


class TestEnforceAuthority:
    def test_no_triggered_actions(self):
        actions = [dict(_make_action("VETO", "security", triggered=False))]
        result = enforce_authority([], actions)
        assert result.overall_status == "OPEN"

    def test_veto_blocks(self):
        actions = [_make_action("VETO", "security")]
        result = enforce_authority([], actions)
        assert result.overall_status == "BLOCKED"
        assert "security" in result.blocked_by
        assert any("[VETO" in c for c in result.mandatory_conditions)

    def test_independent_cannot_be_overruled(self):
        actions = [_make_action("INDEPENDENT", "fg-dpo")]
        result = enforce_authority([], actions)
        assert result.overall_status == "CONDITIONAL_WITH_FLOOR"
        assert "fg-dpo" in result.independent_determinations

    def test_escalation_upgrades_treatment(self):
        actions = [_make_action("ESCALATION", "risk")]
        result = enforce_authority([], actions, current_treatment="standard-review")
        assert result.overall_status == "ESCALATED"
        assert result.treatment_override == "deep-review"

    def test_patient_safety_floor(self):
        actions = [_make_action("PATIENT_SAFETY", "cmio")]
        result = enforce_authority([], actions)
        assert result.patient_safety_floor is True
        assert result.overall_status == "CONDITIONAL_WITH_FLOOR"

    def test_challenge_flags(self):
        actions = [_make_action("CHALLENGE", "redteam")]
        result = enforce_authority([], actions)
        assert result.overall_status == "CHALLENGED"
        assert "redteam" in result.challenge_flags

    def test_veto_takes_precedence_over_challenge(self):
        actions = [_make_action("VETO", "security"), _make_action("CHALLENGE", "redteam")]
        result = enforce_authority([], actions)
        assert result.overall_status == "BLOCKED"

    def test_veto_takes_precedence_over_escalation(self):
        actions = [_make_action("VETO", "security"), _make_action("ESCALATION", "risk")]
        result = enforce_authority([], actions)
        assert result.overall_status == "BLOCKED"
        assert result.escalated is True

    def test_multiple_independent_determinations(self):
        actions = [
            _make_action("INDEPENDENT", "fg-dpo"),
            _make_action("INDEPENDENT", "fg-dpo-2"),
        ]
        result = enforce_authority([], actions)
        assert len(result.independent_determinations) == 2


class TestApplyAuthorityToFindings:
    def test_approve_marked_when_veto_active(self):
        enforcement = AuthorityEnforcementResult(overall_status="BLOCKED", blocked_by=["security"])
        findings = [
            _make_finding("business", "approve"),
            _make_finding("security", "block"),
        ]
        result = apply_authority_to_findings(findings, enforcement)
        assert "authority_conflict" in result[0]
        assert "authority_conflict" not in result[1]

    def test_no_conflict_when_open(self):
        enforcement = AuthorityEnforcementResult(overall_status="OPEN")
        findings = [_make_finding("business", "approve")]
        result = apply_authority_to_findings(findings, enforcement)
        assert "authority_conflict" not in result[0]


class TestAuthoritySummary:
    def test_blocked_summary(self):
        enforcement = AuthorityEnforcementResult(
            overall_status="BLOCKED",
            blocked_by=["security"],
            mandatory_conditions=["[VETO security] No encryption"],
        )
        summary = generate_authority_summary(enforcement)
        assert "VETO" in summary
        assert "geblokkeerd" in summary.lower()

    def test_open_summary(self):
        enforcement = AuthorityEnforcementResult(overall_status="OPEN")
        summary = generate_authority_summary(enforcement)
        assert "Geen" in summary

    def test_escalated_summary(self):
        enforcement = AuthorityEnforcementResult(overall_status="ESCALATED", escalated=True)
        summary = generate_authority_summary(enforcement)
        assert "ESCALATIE" in summary or "geëscaleerd" in summary.lower()

    def test_independent_summary(self):
        enforcement = AuthorityEnforcementResult(
            overall_status="CONDITIONAL_WITH_FLOOR",
            independent_determinations=["fg-dpo"],
        )
        summary = generate_authority_summary(enforcement)
        assert "ONAFHANKELIJK" in summary or "fg-dpo" in summary
