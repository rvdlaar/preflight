"""Tests for preflight.pipeline.quickscan — Quick Scan mode."""

from preflight.pipeline.quickscan import (
    quick_scan,
    QuickScanVerdict,
    QuickScanResult,
)


class TestQuickScan:
    def test_low_risk_proceeds(self):
        r = quick_scan("We need a new coffee machine for the break room")
        assert r.verdict in (
            QuickScanVerdict.PROCEED,
            QuickScanVerdict.PROCEED_WITH_CAUTION,
        )

    def test_clinical_stops(self):
        r = quick_scan("Implement a new clinical decision support system for the ICU")
        assert r.verdict == QuickScanVerdict.STOP_AND_ASSESS
        assert any("clinical-system" in f for f in r.red_flags)

    def test_ai_ml_stops(self):
        r = quick_scan("Build a machine learning model for diagnostics")
        assert r.verdict == QuickScanVerdict.STOP_AND_ASSESS

    def test_patient_data_stops(self):
        r = quick_scan("Store patient data in the cloud")
        assert r.verdict == QuickScanVerdict.STOP_AND_ASSESS

    def test_decommission_clinical_stops(self):
        r = quick_scan("Decommission the HIS clinical information system")
        assert r.verdict == QuickScanVerdict.STOP_AND_ASSESS
        assert any("cmio" in p for p in r.perspectives)

    def test_printer_not_critical(self):
        r = quick_scan("Replace the old printer in the admin office")
        assert (
            r.verdict != QuickScanVerdict.STOP_AND_ASSESS
            or r.classification.impact_level != "critical"
        )

    def test_proceed_has_no_red_flags(self):
        r = quick_scan("Update the office Wi-Fi password policy")
        if r.verdict == QuickScanVerdict.PROCEED:
            assert len(r.red_flags) == 0

    def test_stop_has_recommendation(self):
        r = quick_scan("Implement clinical AI for patient monitoring")
        assert r.verdict == QuickScanVerdict.STOP_AND_ASSESS
        assert r.recommendation
        assert "MANDATORY" in r.recommendation

    def test_classification_populated(self):
        r = quick_scan("Deploy a new payroll system")
        assert r.classification is not None
        assert r.classification.request_type in (
            "new-application",
            "vendor-selection",
            "infrastructure-change",
        )

    def test_estimated_time_varies(self):
        r1 = quick_scan("Replace the printer")
        r2 = quick_scan("Implement clinical AI for ICU patient monitoring")
        if r1.verdict != r2.verdict:
            assert r1.estimated_assessment_time != r2.estimated_assessment_time
