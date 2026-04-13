"""Tests for preflight.synthesis — document triggers, PRODUCT_TRIGGERS."""

from preflight.synthesis.engine import determine_required_documents, PRODUCT_TRIGGERS


class TestProductTriggers:
    def test_always_documents(self):
        docs = determine_required_documents("new-application")
        assert "psa" in docs
        assert "adr" in docs
        assert "operational-readiness" in docs

    def test_clinical_system_triggers(self):
        docs = determine_required_documents("clinical-system")
        assert "clinical-impact" in docs
        assert "dpia" in docs

    def test_ai_ml_triggers_eu_ai_act(self):
        docs = determine_required_documents("ai-ml")
        assert "eu-ai-act" in docs

    def test_decommission_triggers_checklist(self):
        docs = determine_required_documents("decommission")
        assert "decommission-checklist" in docs

    def test_vendor_selection_triggers(self):
        docs = determine_required_documents("vendor-selection")
        assert "vendor-assessment" in docs

    def test_integration_triggers(self):
        docs = determine_required_documents("integration")
        assert "integration-design" in docs

    def test_security_concern_triggers(self):
        docs = determine_required_documents("new-application", {"security": "concern"})
        assert "security-assessment" in docs

    def test_biv_high_triggers_bia(self):
        docs = determine_required_documents(
            "new-application", {}, {"B": 3, "I": 2, "V": 2}
        )
        assert "bia-biv" in docs

    def test_fg_dpo_concern_triggers_dpia(self):
        docs = determine_required_documents("new-application", {"fg-dpo": "concern"})
        assert "dpia" in docs

    def test_tech_radar_for_new_app(self):
        docs = determine_required_documents("new-application")
        assert "tech-radar-update" in docs

    def test_no_tech_radar_for_decommission(self):
        docs = determine_required_documents("decommission")
        assert "tech-radar-update" not in docs

    def test_roadmap_impact_for_architecture_roadmap(self):
        docs = determine_required_documents("architecture-roadmap")
        assert "roadmap-impact" in docs

    def test_portfolio_concern_triggers_roadmap(self):
        docs = determine_required_documents("new-application", {"portfolio": "concern"})
        assert "roadmap-impact" in docs

    def test_product_triggers_declarative(self):
        assert "always" in PRODUCT_TRIGGERS["psa"]
        assert "always" in PRODUCT_TRIGGERS["adr"]
        assert "always" in PRODUCT_TRIGGERS["operational-readiness"]
        assert "decommission" in PRODUCT_TRIGGERS["decommission-checklist"]
