"""
Tests for product data extractor — derives template vars from pipeline output.
"""

import pytest

from preflight.synthesis.product_extractor import (
    extract_security_data,
    extract_clinical_data,
    extract_dpia_data,
    extract_bia_data,
    extract_roadmap_data,
    extract_network_data,
    extract_tech_radar_data,
    extract_integration_data,
    extract_ai_act_data,
    extract_vendor_data,
    extract_decommission_data,
    extract_all_product_data,
)


def _findings(
    persona_id: str, rating: str, findings: list[str], conditions: list[str] | None = None
):
    return {
        "perspective_id": persona_id,
        "name": persona_id.title(),
        "rating": rating,
        "findings": findings,
        "conditions": conditions or [],
    }


PERSONA_FINDINGS_LIS = [
    _findings(
        "security",
        "block",
        [
            "No encryption at rest for patient data",
            "MFA not implemented for admin access",
            "Firewall rules allow broad access between zones",
        ],
        ["Implement encryption at rest for all patient data", "Deploy MFA for admin accounts"],
    ),
    _findings(
        "cmio",
        "concern",
        [
            "Patient safety risk: LIS replaces manual lab process",
            "Cloverleaf integration for HL7 messaging required",
        ],
        ["Validate HL7 message mapping before go-live"],
    ),
    _findings(
        "fg-dpo",
        "concern",
        [
            "Processing of patient data requires AVG Article 6(1)(e) legal basis",
            "Special category health data (Article 9) is processed",
        ],
        ["Complete DPIA before go-live"],
    ),
    _findings(
        "application",
        "conditional",
        [
            "LIS overlaps with existing LIS module in HIS",
            "Tech radar status: Trial — needs assessment",
        ],
    ),
]

BIV_CLINICAL = {"B": 3, "I": 3, "V": 3}


class TestSecurityData:
    def test_encryptie_finding_populated(self):
        data = extract_security_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL)
        assert (
            "encryption" in data["security_encryption_db_transit"].lower()
            or "Security" in data["security_encryption_db_transit"]
        )

    def test_empty_findings_gives_verify_defaults(self):
        data = extract_security_data([], {})
        assert data["security_auth_method"] == "[VERIFY]"
        assert data["security_mfa"] == "[VERIFY]"

    def test_mfa_keyword_detected(self):
        data = extract_security_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL)
        assert "mfa" in data["security_mfa"].lower()


class TestClinicalData:
    def test_cmio_findings_in_summary(self):
        data = extract_clinical_data(
            PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="clinical-system"
        )
        assert "CMIO" in data["clinical_summary"]

    def test_cloverleaf_mentioned(self):
        data = extract_clinical_data(
            PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="clinical-system"
        )
        assert (
            "Cloverleaf" in data["clinical_cloverleaf_integration"]
            or "cloverleaf" in data["clinical_cloverleaf_integration"].lower()
        )

    def test_safety_critical_for_clinical_system(self):
        data = extract_clinical_data(
            PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="clinical-system"
        )
        assert data["clinical_safety_critical"] is True

    def test_biv_rationales_populated(self):
        data = extract_clinical_data(
            PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="clinical-system"
        )
        assert "B=3" in data["clinical_biv_b_rationale"]
        assert "I=3" in data["clinical_biv_i_rationale"]
        assert "V=3" in data["clinical_biv_v_rationale"]


class TestDPIAData:
    def test_patient_data_triggers_art6(self):
        data = extract_dpia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="patient-data")
        assert "Article 6" in data["dpia_art6_rationale"]

    def test_health_data_triggers_art9(self):
        data = extract_dpia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="clinical-system")
        assert "Article 9" in data["dpia_art9_rationale"] or "Verify" in data["dpia_art9_rationale"]

    def test_fg_conditions_extracted(self):
        data = extract_dpia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL, request_type="patient-data")
        assert data["dpia_fg_conditions"] != "[—]"
        assert "DPIA" in data["dpia_fg_conditions"]


class TestBIAData:
    def test_biv_scores_in_rationales(self):
        data = extract_bia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL)
        assert "B=3" in data["bia_b_rationale"]
        assert "I=3" in data["bia_i_rationale"]
        assert "V=3" in data["bia_v_rationale"]

    def test_b3_requirements_populated(self):
        data = extract_bia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL)
        assert "RPO" in data["bia_req_b3_rpo"]
        assert "NEN 7510" in data["bia_req_b3_dr"]

    def test_i3_requirements_populated(self):
        data = extract_bia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL)
        assert "Validati" in data["bia_req_i3_validation"]
        assert "Audit" in data["bia_req_i3_audit"]

    def test_low_biv_no_requirements(self):
        data = extract_bia_data(PERSONA_FINDINGS_LIS, {"B": 1, "I": 1, "V": 1})
        assert data["bia_req_b3_rpo"] == "[Open]"
        assert data["bia_req_i3_validation"] == "[Open]"

    def test_nen_findings_populated(self):
        findings_with_nen = PERSONA_FINDINGS_LIS + [
            _findings("security", "block", ["NEN 7510 baseline niet gehaald", "MFA ontbreekt"]),
        ]
        data = extract_bia_data(findings_with_nen, BIV_CLINICAL)
        assert data["bia_nen7510_rationale"] != ""

    def test_nen_findings_empty_without_mentions(self):
        data = extract_bia_data(PERSONA_FINDINGS_LIS, BIV_CLINICAL)
        assert data["bia_nen7510_rationale"] == ""


class TestRoadmapData:
    def test_app_findings_in_rationale(self):
        data = extract_roadmap_data(PERSONA_FINDINGS_LIS)
        assert data["roadmap_app_rationale"] != ""


class TestNetworkData:
    def test_network_impact_from_persona(self):
        data = extract_network_data(PERSONA_FINDINGS_LIS)
        assert (
            data["network_impact_level"] == ""
            or "netwerk" in data["network_impact_level"].lower()
            or "Hoog" in data["network_impact_level"]
        )

    def test_empty_findings_no_crash(self):
        data = extract_network_data([], None)
        assert "network_system_overview" in data


class TestTechRadarData:
    def test_tech_radar_from_findings(self):
        data = extract_tech_radar_data(PERSONA_FINDINGS_LIS)
        assert data["tech_radar_rationale"] != ""


class TestDecommissionData:
    def test_system_name_from_request(self):
        data = extract_decommission_data(PERSONA_FINDINGS_LIS, None, "LIS Sysmex Decommission")
        assert data["decommission_system_name"] == "LIS Sysmex Decommission"


class TestExtractAll:
    def test_only_required_docs_extracted(self):
        data = extract_all_product_data(
            persona_findings=PERSONA_FINDINGS_LIS,
            biv=BIV_CLINICAL,
            required_documents=["security-assessment", "bia-biv"],
        )
        assert "security_system_overview" in data
        assert "bia_b_rationale" in data
        assert "clinical_patient_impact" not in data

    def test_all_docs(self):
        data = extract_all_product_data(
            persona_findings=PERSONA_FINDINGS_LIS,
            biv=BIV_CLINICAL,
            required_documents=[
                "security-assessment",
                "clinical-impact",
                "dpia",
                "bia-biv",
                "network-impact",
                "roadmap-impact",
                "tech-radar-update",
                "integration-design",
                "eu-ai-act",
                "vendor-assessment",
                "decommission-checklist",
            ],
        )
        assert "security_system_overview" in data
        assert "clinical_summary" in data
        assert "dpia_art6_rationale" in data
        assert "bia_b_rationale" in data
