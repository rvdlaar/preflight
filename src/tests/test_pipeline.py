"""Tests for preflight.pipeline — triage floors, authority, conditions, BIV."""

from preflight.pipeline.pipeline import (
    apply_triage_floors,
    process_authority_actions,
    determine_biv,
    create_conditions,
    all_conditions_met,
    TRIAGE_FLOORS,
)


class TestTriageFloors:
    def test_clinical_cannot_fast_track(self):
        perspectives = ["chief", "security"]
        triage = {"treatment": "fast-track", "reason": "Low risk"}
        p, t = apply_triage_floors("clinical-system", "high", perspectives, triage)
        assert t["treatment"] == "standard-review"
        assert "cmio" in p
        assert "fg-dpo" in p

    def test_patient_data_activates_fg_dpo(self):
        perspectives = ["chief"]
        triage = {"treatment": "fast-track", "reason": ""}
        p, t = apply_triage_floors("patient-data", "medium", perspectives, triage)
        assert "fg-dpo" in p
        assert t["treatment"] == "standard-review"

    def test_standard_request_unchanged(self):
        perspectives = ["chief", "security"]
        triage = {"treatment": "standard-review", "reason": "Default"}
        p, t = apply_triage_floors("new-application", "medium", perspectives, triage)
        assert t["treatment"] == "standard-review"

    def test_critical_adds_redteam(self):
        perspectives = ["chief", "security"]
        triage = {"treatment": "deep-review"}
        p, t = apply_triage_floors("new-application", "critical", perspectives, triage)
        assert "redteam" in p
        assert t["treatment"] == "deep-review"

    def test_high_impact_adds_redteam(self):
        perspectives = ["chief"]
        triage = {"treatment": "standard-review"}
        p, t = apply_triage_floors("new-application", "high", perspectives, triage)
        assert "redteam" in p

    def test_cross_type_clinical_floor(self):
        perspectives = ["chief"]
        triage = {"treatment": "fast-track", "reason": ""}
        p, t = apply_triage_floors(
            "decommission",
            "medium",
            perspectives,
            triage,
            request_text="Decommission the HIS clinical information system",
        )
        assert "cmio" in p
        assert t["treatment"] == "standard-review"

    def test_cross_type_patient_data_floor(self):
        perspectives = ["chief"]
        triage = {"treatment": "fast-track", "reason": ""}
        p, t = apply_triage_floors(
            "integration",
            "medium",
            perspectives,
            triage,
            request_text="Connect to the patient data archive",
        )
        assert "fg-dpo" in p

    def test_cross_type_no_match(self):
        perspectives = ["chief"]
        triage = {"treatment": "fast-track", "reason": "Low risk"}
        p, t = apply_triage_floors(
            "new-application",
            "low",
            perspectives,
            triage,
            request_text="A simple printing solution",
        )
        assert t["treatment"] == "fast-track"

    def test_no_request_text_backwards_compat(self):
        perspectives = ["chief"]
        triage = {"treatment": "standard-review"}
        p, t = apply_triage_floors("new-application", "medium", perspectives, triage)
        assert t["treatment"] == "standard-review"


class TestAuthorityActions:
    def test_veto_detected(self):
        findings = [
            {
                "perspective_id": "security",
                "rating": "block",
                "authority": "VETO",
                "findings": ["Critical vulnerability"],
            }
        ]
        actions = process_authority_actions(findings)
        assert any(a.get("type") == "VETO" and a.get("triggered") for a in actions)

    def test_escalation_detected(self):
        findings = [
            {
                "perspective_id": "risk",
                "rating": "block",
                "authority": "ESCALATION",
                "findings": ["Risk too high"],
            }
        ]
        actions = process_authority_actions(findings)
        assert any(
            a.get("type") == "ESCALATION" and a.get("triggered") for a in actions
        )

    def test_no_authority_triggered(self):
        findings = [
            {"perspective_id": "application", "rating": "approve", "findings": []}
        ]
        actions = process_authority_actions(findings)
        assert not any(a.get("triggered") for a in actions)

    def test_veto_not_triggered_on_non_block(self):
        findings = [
            {
                "perspective_id": "security",
                "rating": "concern",
                "authority": "VETO",
                "findings": ["Issue"],
            }
        ]
        actions = process_authority_actions(findings)
        assert not any(a.get("type") == "VETO" and a.get("triggered") for a in actions)

    def test_cmio_patient_safety_floor(self):
        findings = [
            {
                "perspective_id": "cmio",
                "rating": "conditional",
                "authority": "PATIENT_SAFETY",
                "findings": ["Clinical workflow impact"],
            }
        ]
        actions = process_authority_actions(findings)
        assert any(
            a.get("type") == "PATIENT_SAFETY" and a.get("triggered") for a in actions
        )


class TestBIV:
    def test_default_biv(self):
        findings = [{"perspective_id": "application", "rating": "approve"}]
        biv = determine_biv(findings, "new-application")
        assert "B" in biv
        assert "I" in biv
        assert "V" in biv

    def test_clinical_system_high_biv(self):
        findings = [
            {
                "perspective_id": "cmio",
                "rating": "concern",
                "findings": ["Patient safety risk"],
            }
        ]
        biv = determine_biv(findings, "clinical-system")
        assert biv["B"] >= 2


class TestConditions:
    def test_conditions_created_open(self):
        findings = [
            {
                "perspective_id": "security",
                "rating": "conditional",
                "conditions": ["Must implement MFA"],
                "name": "Victor",
            }
        ]
        conditions = create_conditions(findings, "PSA-20260410")
        assert len(conditions) == 1
        assert conditions[0]["status"] == "OPEN"
        assert conditions[0]["source_persona"] == "Victor"

    def test_all_conditions_met(self):
        conditions = [
            {"status": "MET"},
            {"status": "MET"},
        ]
        assert all_conditions_met(conditions) is True

    def test_not_all_conditions_met(self):
        conditions = [
            {"status": "MET"},
            {"status": "OPEN"},
        ]
        assert all_conditions_met(conditions) is False
