"""Tests for preflight.classify — classification, dual classification, heuristics."""

from preflight.classify.classify import (
    classify_request,
    classify_request_dual,
    ClassificationResult,
    DualClassificationResult,
    _heuristic_classify,
    select_relevant_perspectives,
    REQUEST_TYPES,
    IMPACT_LEVELS,
)


class TestHeuristicClassify:
    def test_clinical_system_detected(self):
        r = _heuristic_classify(
            "We want to implement a clinical decision support system"
        )
        assert r.request_type == "clinical-system"
        assert r.impact_level == "high"
        assert r.method == "heuristic"

    def test_ai_ml_detected(self):
        r = _heuristic_classify(
            "Deploy a machine learning model for predictive analytics"
        )
        assert r.request_type == "ai-ml"
        assert r.impact_level == "high"

    def test_integration_detected(self):
        r = _heuristic_classify("Build an HL7 FHIR interface to the new lab system")
        assert r.request_type == "integration"

    def test_patient_data_upgrades_impact(self):
        r = _heuristic_classify("Store patient data in a new cloud platform")
        assert r.impact_level in ("medium", "high")

    def test_new_application_default(self):
        r = _heuristic_classify("We need a new invoicing system for finance")
        assert r.request_type in ("new-application", "vendor-selection")
        assert r.impact_level in ("low", "medium")

    def test_confidence_is_moderate(self):
        r = _heuristic_classify("Replace the printer")
        assert r.confidence == 0.5

    def test_decommission_detected(self):
        r = _heuristic_classify("Retire the legacy RIS system")
        assert r.request_type == "decommission"

    def test_critical_impact_only_for_life_critical(self):
        r = _heuristic_classify("Replace the old printer in the admin office")
        assert r.impact_level != "critical"

    def test_manufacturing_ot(self):
        r = _heuristic_classify("Connect SCADA to the MES production system")
        assert r.request_type == "manufacturing-ot"

    def test_dutch_keywords(self):
        r = _heuristic_classify("We willen patiëntenzorg data opslaan")
        assert r.request_type in ("patient-data", "clinical-system")


class TestSelectRelevantPerspectives:
    def test_clinical_gets_cmio(self):
        p = select_relevant_perspectives("clinical-system", "high")
        assert "cmio" in p
        assert "fg-dpo" in p

    def test_high_impact_adds_redteam(self):
        p = select_relevant_perspectives("new-application", "high")
        assert "redteam" in p

    def test_critical_adds_cmio(self):
        p = select_relevant_perspectives("ai-ml", "critical")
        assert "cmio" in p

    def test_low_impact_no_redteam(self):
        p = select_relevant_perspectives("new-application", "low")
        assert "redteam" not in p

    def test_core_always_present(self):
        for rt in REQUEST_TYPES:
            p = select_relevant_perspectives(rt, "medium")
            assert "risk" in p, f"Missing core perspective 'risk' for {rt}"


class TestClassificationResult:
    def test_default_method(self):
        r = ClassificationResult(request_type="new-application", impact_level="medium")
        assert r.method == "llm"
        assert r.dual is False
        assert r.divergence is None

    def test_dual_fields(self):
        r = ClassificationResult(
            request_type="clinical-system",
            impact_level="high",
            dual=True,
            divergence="type",
        )
        assert r.dual is True
        assert r.divergence == "type"


class TestDualClassificationResult:
    def test_agreement_merged(self):
        primary = ClassificationResult(
            request_type="clinical-system",
            impact_level="high",
            confidence=0.9,
            keywords=["his"],
        )
        secondary = ClassificationResult(
            request_type="clinical-system",
            impact_level="high",
            confidence=0.85,
            keywords=["pacs"],
        )
        dual = DualClassificationResult(
            primary=primary, secondary=secondary, agreement=True
        )
        merged = dual.merged
        assert merged.request_type == "clinical-system"
        assert merged.impact_level == "high"
        assert "his" in merged.keywords
        assert "pacs" in merged.keywords
        assert merged.method == "llm-dual-agree"

    def test_disagreement_escelates_impact(self):
        primary = ClassificationResult(
            request_type="new-application", impact_level="medium", confidence=0.7
        )
        secondary = ClassificationResult(
            request_type="integration", impact_level="high", confidence=0.8
        )
        dual = DualClassificationResult(
            primary=primary,
            secondary=secondary,
            agreement=False,
            divergence_type="both",
            divergence_detail="type vs impact",
        )
        merged = dual.merged
        assert merged.impact_level == "high"
        assert merged.confidence < 0.8
        assert merged.dual is True
        assert merged.method == "llm-dual-disagree"

    def test_no_secondary(self):
        primary = ClassificationResult(
            request_type="new-application", impact_level="medium"
        )
        dual = DualClassificationResult(primary=primary)
        assert dual.agreement is True
        merged = dual.merged
        assert merged.request_type == "new-application"
