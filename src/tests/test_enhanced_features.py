"""Tests for principetoets, BIV cascades, verwerkingsregister, API endpoints."""

from preflight.pipeline.pipeline import (
    generate_principetoets,
    determine_biv,
    derive_biv_controls,
    create_conditions,
    generate_verwerkingsregister_draft,
    can_transition,
    LIFECYCLE_STATES,
    VALID_TRANSITIONS,
)


class TestPrincipetoets:
    def test_approve_gives_voldoet(self):
        findings = [
            {
                "name": "Sophie",
                "perspective_id": "business",
                "rating": "approve",
                "findings": ["Good"],
            }
        ]
        result = generate_principetoets(findings)
        assert result["satisfied"] >= 1
        p1 = [p for p in result["principles"] if p["number"] == 1][0]
        assert p1["assessment"] == "Voldoet"

    def test_block_gives_niet(self):
        findings = [
            {
                "name": "Victor",
                "perspective_id": "security",
                "rating": "block",
                "findings": ["Vuln"],
            }
        ]
        result = generate_principetoets(findings)
        assert result["unsatisfied"] >= 1
        p2 = [p for p in result["principles"] if p["number"] == 2][0]
        assert p2["assessment"] == "Niet"

    def test_concern_gives_deels(self):
        findings = [
            {
                "name": "Jan",
                "perspective_id": "infrastructure",
                "rating": "concern",
                "findings": ["Risk"],
            }
        ]
        result = generate_principetoets(findings)
        assert result["partial"] >= 1

    def test_all_12_principles_evaluated(self):
        result = generate_principetoets([])
        assert len(result["principles"]) == 12
        assert all("definition" in p for p in result["principles"])

    def test_mixed_ratings(self):
        findings = [
            {
                "name": "Victor",
                "perspective_id": "security",
                "rating": "block",
                "findings": ["Vuln"],
            },
            {
                "name": "Sophie",
                "perspective_id": "business",
                "rating": "approve",
                "findings": ["Good"],
            },
            {
                "name": "Jan",
                "perspective_id": "infrastructure",
                "rating": "concern",
                "findings": ["Risk"],
            },
        ]
        result = generate_principetoets(findings)
        assert result["unsatisfied"] >= 1
        assert result["satisfied"] >= 1
        assert result["partial"] >= 1


class TestBIVCascades:
    def test_high_biv_generates_conditions(self):
        biv = {"B": 3, "I": 3, "V": 2}
        controls = derive_biv_controls(biv)
        assert len(controls) >= 8

    def test_biv_cascades_in_conditions(self):
        biv = {"B": 3, "I": 2, "V": 2}
        controls = derive_biv_controls(biv)
        conditions = create_conditions(
            [
                {
                    "name": "Victor",
                    "role": "Security",
                    "conditions": ["MFA required"],
                    "rating": "block",
                }
            ],
            "PSA-TEST",
            biv_controls=controls,
        )
        biv_conditions = [
            c
            for c in conditions
            if "[BIV]" in c.get("condition_text", c.get("condition", ""))
        ]
        assert len(biv_conditions) >= 3
        assert any(
            "RPO" in c.get("condition_text", c.get("condition", ""))
            for c in biv_conditions
        )

    def test_no_biv_controls_for_low(self):
        biv = {"B": 1, "I": 1, "V": 1}
        controls = derive_biv_controls(biv)
        assert len(controls) == 0

    def test_biv_3_has_dr_plan(self):
        biv = {"B": 3, "I": 2, "V": 2}
        controls = derive_biv_controls(biv)
        assert any("Disaster Recovery" in c["requirement"] for c in controls)


class TestVerwerkingsregister:
    def test_draft_generated(self):
        result = generate_verwerkingsregister_draft(
            proposal_name="Digital Pathology",
            processing_description="Processing patient pathology images",
            data_categories=["BSN", "medische beelden"],
            purpose="Clinical diagnostics",
            legal_basis="AVG Artikel 6 lid 1 sub e",
            data_subjects=["Patiënten"],
            retention_period="10 jaar conform WGBO",
        )
        assert result["status"] == "CONCEPT — FG-bepaling vereist"
        assert result["review_required"] is True
        assert result["reviewer"] == "FG-DPO"
        assert "BSN" in result["entry"]["categorie_persoonsgegevens"]

    def test_default_placeholders(self):
        result = generate_verwerkingsregister_draft()
        assert "[Beschrijving" in result["entry"]["verwerkingsactiviteit"]
        assert result["review_required"] is True


class TestLifecycleTransitions:
    def test_valid_transitions(self):
        assert can_transition("SUBMITTED", "PRELIMINARY")
        assert can_transition("ASSESSED", "BOARD_READY")
        assert can_transition("DECIDED", "CLOSED")

    def test_invalid_transitions(self):
        assert not can_transition("SUBMITTED", "ASSESSED")
        assert not can_transition("CLOSED", "SUBMITTED")
        assert not can_transition("IN_REVIEW", "ASSESSED")

    def test_all_states(self):
        assert len(LIFECYCLE_STATES) == 9
        assert "SUBMITTED" in LIFECYCLE_STATES
        assert "CLOSED" in LIFECYCLE_STATES
