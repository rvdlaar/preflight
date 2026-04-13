"""Tests for landscape context scoping, deep mode parser integration, and API persistence."""

from preflight.pipeline.orchestrator import (
    _scope_landscape_per_persona,
    LANDSCAPE_SCOPE_MAP,
    parse_fast_assessment,
)
from preflight.llm.parser import parse_deep_assessment
from preflight.pipeline.pipeline import (
    process_authority_actions,
    create_conditions,
    TRIAGE_FLOORS,
    apply_triage_floors,
)


class TestLandscapeScoping:
    LANDSCAPE = {
        "existingApps": ["Epic", "Cloverleaf", "JiveX"],
        "relatedInterfaces": ["HL7", "FHIR", "DICOM"],
        "openRisks": ["Patient data exposure in Cloverleaf", "BSN leak risk"],
        "techRadarStatus": "Epic: Adopt, Cloverleaf: Trial, JiveX: Assess",
        "capabilityMap": "Epic → Clinical, Cloverleaf → Integration, JiveX → Radiology",
        "cascadeDeps": ["Cloverleaf → Epic", "JiveX → Cloverleaf"],
        "recentChanges": [],
        "raw": {
            "existingApps": [],
            "interfaces": [],
            "dataObjects": [],
            "cascadeDeps": [],
        },
    }

    def test_scope_map_has_all_22_personas(self):
        assert len(LANDSCAPE_SCOPE_MAP) == 22

    def test_security_gets_risks_and_cascade(self):
        scoped = _scope_landscape_per_persona(self.LANDSCAPE)
        assert "security" in scoped
        assert "openRisks" in scoped["security"]
        assert "Patient data exposure" in scoped["security"]

    def test_data_gets_risks_and_raw(self):
        scoped = _scope_landscape_per_persona(self.LANDSCAPE)
        assert "data" in scoped
        assert "openRisks" in scoped["data"]

    def test_application_gets_apps_and_tech(self):
        scoped = _scope_landscape_per_persona(self.LANDSCAPE)
        assert "application" in scoped
        assert "existingApps" in scoped["application"]
        assert "Epic" in scoped["application"]

    def test_integration_gets_interfaces(self):
        scoped = _scope_landscape_per_persona(self.LANDSCAPE)
        assert "integration" in scoped
        assert "relatedInterfaces" in scoped["integration"]

    def test_empty_landscape_returns_empty(self):
        scoped = _scope_landscape_per_persona(None)
        assert scoped == {}

    def test_string_landscape_returns_empty(self):
        scoped = _scope_landscape_per_persona("some text")
        assert scoped == {}

    def test_all_personas_get_content(self):
        scoped = _scope_landscape_per_persona(self.LANDSCAPE)
        assert len(scoped) >= 15

    def test_redteam_gets_risks_and_cascade(self):
        scoped = _scope_landscape_per_persona(self.LANDSCAPE)
        assert "redteam" in scoped
        assert "openRisks" in scoped["redteam"]
        assert "cascadeDeps" in scoped["redteam"]


class TestAuthorityActionsExtended:
    def test_independent_always_triggered(self):
        findings = [
            {
                "perspective_id": "fg-dpo",
                "rating": "approve",
                "authority": "INDEPENDENT",
                "findings": ["All clear"],
            }
        ]
        actions = process_authority_actions(findings)
        assert any(
            a.get("type") == "INDEPENDENT" and a.get("triggered") for a in actions
        )

    def test_challenge_not_in_authority_types(self):
        findings = [
            {
                "perspective_id": "business",
                "rating": "concern",
                "findings": ["Some issue"],
            }
        ]
        actions = process_authority_actions(findings)
        assert not any(a.get("triggered") for a in actions)

    def test_multiple_authority_actions(self):
        findings = [
            {
                "perspective_id": "security",
                "rating": "block",
                "authority": "VETO",
                "findings": ["Critical"],
            },
            {
                "perspective_id": "risk",
                "rating": "block",
                "authority": "ESCALATION",
                "findings": ["High risk"],
            },
        ]
        actions = process_authority_actions(findings)
        types = [a.get("type") for a in actions]
        assert "VETO" in types
        assert "ESCALATION" in types

    def test_explicit_authority_overrides_default(self):
        findings = [
            {
                "perspective_id": "data",
                "rating": "concern",
                "authority": "VETO",
                "findings": ["Data leak"],
            }
        ]
        actions = process_authority_actions(findings)
        assert any(a.get("type") == "VETO" for a in actions)


class TestConditionsExtended:
    def test_conditions_from_dict_format(self):
        findings = [
            {
                "perspective_id": "security",
                "name": "Victor",
                "conditions": [{"condition": "Encrypt at rest", "priority": "high"}],
                "rating": "conditional",
            }
        ]
        conditions = create_conditions(findings, "PSA-TEST-001")
        assert len(conditions) == 1
        assert conditions[0]["condition_text"] == "Encrypt at rest"
        assert conditions[0]["status"] == "OPEN"

    def test_conditions_skip_none_entries(self):
        findings = [
            {
                "perspective_id": "business",
                "name": "Sophie",
                "conditions": ["Good", "none", "N/A", "", "Valid condition"],
                "rating": "approve",
            }
        ]
        conditions = create_conditions(findings, "PSA-TEST-001")
        texts = [c["condition_text"] for c in conditions]
        assert "Good" in texts
        assert "Valid condition" in texts
        assert "none" not in [t.lower() for t in texts]

    def test_biv_controls_in_conditions(self):
        from preflight.pipeline.pipeline import derive_biv_controls

        biv = {"B": 3, "I": 3, "V": 2}
        controls = derive_biv_controls(biv)
        conditions = create_conditions([], "PSA-TEST-001", biv_controls=controls)
        biv_conds = [c for c in conditions if "[BIV]" in c["condition_text"]]
        assert len(biv_conds) >= 3


class TestTriageFloorsExtended:
    def test_decommission_floor(self):
        p, t = apply_triage_floors(
            "decommission",
            "medium",
            ["chief"],
            {"treatment": "fast-track", "reason": ""},
        )
        assert "process" in p
        assert "business" in p
        assert t["treatment"] == "standard-review"

    def test_patient_data_adds_privacy(self):
        p, t = apply_triage_floors(
            "patient-data", "low", ["chief"], {"treatment": "fast-track", "reason": ""}
        )
        assert "fg-dpo" in p
        assert "privacy" in p

    def test_no_double_downgrade(self):
        p, t = apply_triage_floors(
            "clinical-system",
            "critical",
            ["chief"],
            {"treatment": "deep-review", "reason": ""},
        )
        assert t["treatment"] == "deep-review"

    def test_cross_type_no_false_positive(self):
        p, t = apply_triage_floors(
            "new-application",
            "low",
            ["chief"],
            {"treatment": "fast-track", "reason": "Low risk"},
            request_text="A simple printing solution for office documents",
        )
        assert t["treatment"] == "fast-track"

    def test_all_triage_floor_keys_valid(self):
        for key in TRIAGE_FLOORS:
            assert "add_perspectives" in TRIAGE_FLOORS[key]
            assert "minimum_treatment" in TRIAGE_FLOORS[key]
            assert "reason" in TRIAGE_FLOORS[key]
            assert TRIAGE_FLOORS[key]["minimum_treatment"] in (
                "standard-review",
                "deep-review",
            )
