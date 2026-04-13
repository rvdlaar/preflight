"""
Product data extractor — derives template-specific variables from pipeline output.

The templates have 148 variables that build_document_context doesn't populate.
This module derives them by mining persona_findings, classification, BIV,
authority actions, and landscape context. Where data can't be derived, the
[ARCHITECT INPUT NEEDED] default stays — that's intentional.

Thinking applied:
  First principles: Persona findings contain rich structured text. The security
  persona talks about encryption. The CMIO talks about patient safety. The FG/DPO
  talks about legal bases. We extract these into product-specific fields.
  Second order: LLM output is noisy. Keywords like "encryption" might appear
  in a non-security context. We weight findings by persona domain — security
  persona findings about encryption > business persona findings about encryption.
  Inversion: What if extraction produces wrong values? E.g., extracting "yes"
  for MFA when the persona actually said "no MFA present". We prefix uncertain
  extractions with [VERIFY] so the architect knows to check.
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

PERSONA_DOMAIN = {
    "security": [
        "encryption",
        "auth",
        "mfa",
        "firewall",
        "vpn",
        "certificate",
        "patch",
        "vulnerability",
        "pentest",
        "hardening",
    ],
    "risk": ["risk", "compliance", "audit", "control", "governance", "nen", "baseline"],
    "fg-dpo": [
        "privacy",
        "avg",
        "gdpr",
        "persoonsgegevens",
        "verwerking",
        "grondslag",
        "dpia",
        "consent",
    ],
    "cmio": [
        "patient",
        "kliniek",
        "patiëntveiligheid",
        "medisch",
        "diagnostiek",
        "hl7",
        "fhir",
        "epd",
    ],
    "cio": ["strategy", "budget", "tco", "roadmap", "portfolio", "investering"],
    "business": ["business", "bedrijfsfunctie", "waarde", "stakeholder", "proces"],
    "process": ["workflow", "proces", "handover", "traceerbaarheid", "wegiz"],
    "application": ["application", "saaS", "vendor", "lifecycle", "overlap", "tech radar"],
    "information": ["data", "informatie", "kwaliteit", "semantiek", "integriteit"],
    "network": ["network", "netwerk", "vlan", " firewall", "zone", "bandwidth", "latency"],
    "portfolio": ["portfolio", "roadmap", "capability", "gap", "overlap", "rationalisatie"],
    "redteam": ["grouptthink", "assumption", "cascade", "failure", "pre-mortem"],
}


def _find_in_findings(
    persona_findings: list[dict],
    keywords: list[str],
    persona_ids: list[str] | None = None,
) -> list[str]:
    """Extract sentences from persona findings that match keywords."""
    results = []
    for pf in persona_findings:
        pid = pf.get("perspective_id", "")
        if persona_ids and pid not in persona_ids:
            continue
        for finding in pf.get("findings", []):
            text = finding if isinstance(finding, str) else finding.get("finding", "")
            lower = text.lower()
            if any(kw.lower() in lower for kw in keywords):
                results.append(text)
    return results


def _first_match(texts: list[str], pattern: str, default: str = "") -> str:
    """Find first text matching regex pattern."""
    for t in texts:
        m = re.search(pattern, t, re.IGNORECASE)
        if m:
            return m.group(1) if m.groups() else t
    return default


def _has_keyword(
    persona_findings: list[dict], keywords: list[str], persona_ids: list[str] | None = None
) -> bool:
    """Check if any finding mentions keywords."""
    return bool(_find_in_findings(persona_findings, keywords, persona_ids))


def _extract_conditions_for(persona_findings: list[dict], keywords: list[str]) -> list[str]:
    """Extract conditions from persona findings matching keywords."""
    results = []
    for pf in persona_findings:
        for cond in pf.get("conditions", []):
            text = (
                cond
                if isinstance(cond, str)
                else cond.get("condition", cond.get("condition_text", ""))
            )
            lower = text.lower()
            if any(kw.lower() in lower for kw in keywords):
                results.append(text)
    return results


# ---------------------------------------------------------------------------
# Security assessment product data
# ---------------------------------------------------------------------------


def extract_security_data(
    persona_findings: list[dict],
    biv: dict,
    landscape: dict | None = None,
) -> dict[str, Any]:
    sec_findings = _find_in_findings(
        persona_findings,
        ["encryption", "auth", "mfa", "firewall", "vpn", "certificate", "patch", "hardening"],
        persona_ids=["security", "risk"],
    )

    data: dict[str, Any] = {}

    data["security_system_overview"] = ""
    if landscape:
        apps = landscape.get("existingApps", [])
        if apps:
            app_names = ", ".join(a.get("name", "?") for a in apps[:5])
            data["security_system_overview"] = f"[VERIFY] Relevant applications: {app_names}"

    sec_texts = [f[:200] for f in sec_findings[:5]]
    data["security_auth_method"] = _first_match(
        sec_texts, r"auth(?:enticat\w+)?[:\s]+([^.]+)", "[VERIFY]"
    )
    data["security_auth_assessment"] = "[VERIFY]"
    data["security_mfa"] = "[VERIFY]"
    data["security_mfa_assessment"] = "[VERIFY]"
    if _has_keyword(persona_findings, ["mfa", "multi.factor", "twee.factor", "2fa"], ["security"]):
        data["security_mfa"] = "[VERIFY] MFA mentioned in security assessment — confirm status"
    data["security_authz_model"] = _first_match(
        sec_texts, r"authoriz(?:at\w+)?[:\s]+([^.]+)", "[VERIFY]"
    )
    data["security_authz_assessment"] = "[VERIFY]"

    enc_findings = _find_in_findings(
        persona_findings, ["encryption", "encryptie", "tls", "ssl", "versleuteling"], ["security"]
    )
    data["security_encryption_db_rest"] = "[VERIFY]"
    data["security_encryption_db_transit"] = "[VERIFY]"
    data["security_encryption_db_assessment"] = "[VERIFY]"
    data["security_encryption_file_rest"] = "[VERIFY]"
    data["security_encryption_file_assessment"] = "[VERIFY]"
    data["security_encryption_backup_rest"] = "[VERIFY]"
    data["security_encryption_backup_assessment"] = "[VERIFY]"
    if enc_findings:
        combined = "; ".join(enc_findings[:3])
        data["security_encryption_db_transit"] = (
            f"[VERIFY] Security persona findings: {combined[:200]}"
        )

    return data


# ---------------------------------------------------------------------------
# Clinical impact product data
# ---------------------------------------------------------------------------


def extract_clinical_data(
    persona_findings: list[dict],
    biv: dict,
    landscape: dict | None = None,
    request_type: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    cmio_findings = _find_in_findings(
        persona_findings,
        ["patient", "kliniek", "patiënt", "medisch", "diagnostiek"],
        persona_ids=["cmio"],
    )

    all_clinical = _find_in_findings(
        persona_findings,
        [
            "patient",
            "kliniek",
            "patiëntveiligheid",
            "medisch",
            "hl7",
            "fhir",
            "epd",
            "cloverleaf",
            "jivex",
        ],
    )

    data["clinical_summary"] = ""
    if cmio_findings:
        data["clinical_summary"] = f"[VERIFY] CMIO findings: {'; '.join(cmio_findings[:2])}"

    data["clinical_patient_impact"] = "[VERIFY]"
    data["clinical_failure_risk"] = "[VERIFY]"
    data["clinical_fallback"] = "[VERIFY]"
    data["clinical_safety_critical"] = request_type == "clinical-system"

    if _has_keyword(persona_findings, ["cloverleaf"], ["cmio", "application", "integration"]):
        data["clinical_cloverleaf_integration"] = "[VERIFY] Cloverleaf integration mentioned"
        data["clinical_cloverleaf_impact"] = "[VERIFY]"
    else:
        data["clinical_cloverleaf_integration"] = "[—]"
        data["clinical_cloverleaf_impact"] = "[—]"

    if _has_keyword(persona_findings, ["jivex", "pacs"], ["cmio", "application"]):
        data["clinical_jivex_integration"] = "[VERIFY] JiveX/PACS integration mentioned"
        data["clinical_jivex_impact"] = "[VERIFY]"
    else:
        data["clinical_jivex_integration"] = "[—]"
        data["clinical_jivex_impact"] = "[—]"

    if _has_keyword(persona_findings, ["epd", "ehr", "electronic health"], ["cmio", "application"]):
        data["clinical_ehr_integration"] = "[VERIFY] EHR integration mentioned"
        data["clinical_ehr_impact"] = "[VERIFY]"
    else:
        data["clinical_ehr_integration"] = "[—]"
        data["clinical_ehr_impact"] = "[—]"

    data["clinical_biv_b_rationale"] = (
        f"[VERIFY] B={biv.get('B', '?')} — {'High availability required' if biv.get('B', 0) >= 3 else 'Standard availability'}"
    )
    data["clinical_biv_i_rationale"] = (
        f"[VERIFY] I={biv.get('I', '?')} — {'High integrity required' if biv.get('I', 0) >= 3 else 'Standard integrity'}"
    )
    data["clinical_biv_v_rationale"] = (
        f"[VERIFY] V={biv.get('V', '?')} — {'High confidentiality required' if biv.get('V', 0) >= 3 else 'Standard confidentiality'}"
    )
    data["clinical_workflow_change_risk"] = "[VERIFY]"
    data["clinical_workflow_change_rationale"] = "[—]"
    data["clinical_learning_curve_risk"] = "[VERIFY]"
    data["clinical_learning_curve_rationale"] = "[—]"
    data["clinical_training_risk"] = "[VERIFY]"
    data["clinical_training_rationale"] = "[—]"

    return data


# ---------------------------------------------------------------------------
# DPIA product data
# ---------------------------------------------------------------------------


def extract_dpia_data(
    persona_findings: list[dict],
    biv: dict,
    request_type: str = "",
    language: str = "nl",
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    fg_findings = _find_in_findings(
        persona_findings,
        ["privacy", "avg", "gdpr", "persoonsgegevens", "verwerking", "grondslag"],
        persona_ids=["fg-dpo"],
    )

    data["dpia_controller"] = "[ziekenhuisnaam]"
    data["dpia_department"] = "[VERIFY]"
    data["dpia_vendor"] = "[VERIFY]"
    data["dpia_trigger"] = "[VERIFY]"

    patient_data = request_type in ("patient-data", "clinical-system") or _has_keyword(
        persona_findings, ["persoonsgegevens", "patient data", "patientgegevens"]
    )

    data["dpia_art6_rationale"] = "[VERIFY]"
    if patient_data:
        data["dpia_art6_rationale"] = (
            "[VERIFY] Article 6(1)(e) — processing necessary for task in public interest (healthcare)"
        )

    data["dpia_art9_rationale"] = "[VERIFY]"
    if _has_keyword(
        persona_findings, ["bijzondere", "gezondheid", "special category", "health data"]
    ):
        data["dpia_art9_rationale"] = (
            "[VERIFY] Article 9(2)(h) — processing necessary for healthcare purposes (AIVG 2022)"
        )

    data["dpia_primary_purpose"] = "[VERIFY]"
    data["dpia_secondary_purpose"] = "[—]"
    data["dpia_necessity"] = "[VERIFY]"
    data["dpia_data_minimization"] = "[VERIFY]"
    data["dpia_alternatives"] = "[VERIFY]"
    data["dpia_proportionality"] = "[VERIFY]"
    data["dpia_residual_risk"] = "[VERIFY]"

    for right in ["access", "rectification", "erasure"]:
        data[f"dpia_right_{right}"] = "[VERIFY]"
        data[f"dpia_right_{right}_how"] = "[—]"

    for right in ["restriction", "portability", "objection"]:
        data[f"dpia_right_{right}"] = "[—]"
        data[f"dpia_right_{right}_how"] = "[—]"

    fg_conditions = _extract_conditions_for(
        persona_findings,
        [
            "privacy",
            "avg",
            "gdpr",
            "persoonsgegevens",
            "verwerking",
            "grondslag",
            "dpia",
            "consent",
            "bescherming",
        ],
    )
    data["dpia_fg_conditions"] = ""
    if fg_conditions:
        data["dpia_fg_conditions"] = "; ".join(fg_conditions[:5])
    else:
        data["dpia_fg_conditions"] = "[—]"

    data["dpia_prior_consultation"] = "[VERIFY]"

    return data


# ---------------------------------------------------------------------------
# BIA/BIV product data
# ---------------------------------------------------------------------------


def extract_bia_data(
    persona_findings: list[dict],
    biv: dict,
    biv_controls: list[dict] | dict | None = None,
    language: str = "nl",
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    b = biv.get("B", 2)
    i = biv.get("I", 2)
    v = biv.get("V", 2)

    data["bia_b_assessor"] = "[VERIFY]"
    data["bia_b_rationale"] = (
        f"[VERIFY] B={b} — {'Business continuity critical' if b >= 3 else 'Standard availability requirement'}"
    )
    data["bia_i_assessor"] = "[VERIFY]"
    data["bia_i_rationale"] = (
        f"[VERIFY] I={i} — {'Data integrity critical' if i >= 3 else 'Standard integrity requirement'}"
    )
    data["bia_v_assessor"] = "[VERIFY]"
    data["bia_v_rationale"] = (
        f"[VERIFY] V={v} — {'Confidentiality critical (patient data)' if v >= 3 else 'Standard confidentiality requirement'}"
    )

    data["bia_current_rpo"] = "[VERIFY]"
    data["bia_rpo_gap"] = "[VERIFY]"
    data["bia_current_rto"] = "[VERIFY]"
    data["bia_rto_gap"] = "[VERIFY]"
    data["bia_mtpd"] = "[VERIFY]"

    data["bia_nis2_applicable"] = "[VERIFY]"
    data["bia_nis2_rationale"] = "[—]"
    data["bia_igj_applicable"] = "[VERIFY]"
    data["bia_igj_rationale"] = "[—]"
    data["bia_ap_applicable"] = "[VERIFY]"
    data["bia_ap_rationale"] = "[—]"

    nen_findings = _find_in_findings(
        persona_findings,
        [
            "nen 7510",
            "nen 7512",
            "nen 7513",
            "nta 7516",
            "7510",
            "7512",
            "7513",
            "7516",
            "baseline",
            "informatiebeveiliging",
        ],
        persona_ids=["security", "risk"],
    )
    data["bia_nen7510_applicable"] = "[VERIFY]"
    data["bia_nen7510_rationale"] = ""
    if nen_findings:
        data["bia_nen7510_rationale"] = f"[VERIFY] NEN findings: {'; '.join(nen_findings[:2])}"

    data["bia_wkkgz_applicable"] = "[VERIFY]"
    data["bia_wkkgz_rationale"] = "[—]"

    data["bia_ha_status"] = "[VERIFY]"
    data["bia_ha_owner"] = "[—]"
    data["bia_ha_rationale"] = "[—]"
    data["bia_dr_status"] = "[VERIFY]"
    data["bia_dr_owner"] = "[—]"
    data["bia_dr_rationale"] = "[—]"
    data["bia_backup_status"] = "[VERIFY]"
    data["bia_backup_owner"] = "[—]"
    data["bia_backup_rationale"] = "[—]"

    if b >= 3:
        data["bia_req_b3_rpo"] = "[VERIFY] NEN 7510: RPO ≤ 24u voor B=3 systemen"
        data["bia_req_b3_dr"] = "[VERIFY] NEN 7510: DR plan vereist voor B=3 systemen"
        data["bia_req_b3_iso22301"] = "[Open]"
    else:
        data["bia_req_b3_rpo"] = "[Open]"
        data["bia_req_b3_dr"] = "[Open]"
        data["bia_req_b3_iso22301"] = "[Open]"

    if i >= 3:
        data["bia_req_i3_validation"] = "[VERIFY] NEN 7512: Validatieregels vereist voor I=3"
        data["bia_req_i3_audit"] = "[VERIFY] NEN 7513: Audit logging vereist voor I=3"
    else:
        data["bia_req_i3_validation"] = "[Open]"
        data["bia_req_i3_audit"] = "[Open]"

    if v >= 3:
        data["bia_req_v3_nen7510"] = "[VERIFY] NEN 7510: Toegangsbeheer vereist voor V=3"
        data["bia_req_v3_encryption"] = "[VERIFY] Versleuteling in rust en transit vereist"
        data["bia_req_v3_nen7513"] = "[VERIFY] NEN 7513: Audit logging patiëntdata vereist"
    else:
        data["bia_req_v3_nen7510"] = "[Open]"
        data["bia_req_v3_encryption"] = "[Open]"
        data["bia_req_v3_nen7513"] = "[Open]"

    cascade_findings = _find_in_findings(
        persona_findings, ["cascade", "afhankelijkheid", "dependency", "single.point", "keten"]
    )
    data["bia_cascade_risk"] = ""
    if cascade_findings:
        data["bia_cascade_risk"] = f"[VERIFY] {'; '.join(cascade_findings[:2])}"
    else:
        data["bia_cascade_risk"] = "[VERIFY]"

    return data


# ---------------------------------------------------------------------------
# Roadmap impact product data
# ---------------------------------------------------------------------------


def extract_roadmap_data(
    persona_findings: list[dict],
    classification: Any | None = None,
    landscape: dict | None = None,
    principetoets: list[dict] | dict | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    app_findings = _find_in_findings(
        persona_findings,
        ["portfolio", "overlap", "rationalisatie", "redundantie", "duplicate"],
        persona_ids=["application", "portfolio", "cio"],
    )

    data["roadmap_app_fit"] = "[VERIFY]"
    data["roadmap_app_gap"] = "[—]"
    data["roadmap_app_rationale"] = ""
    if app_findings:
        data["roadmap_app_rationale"] = f"[VERIFY] {'; '.join(app_findings[:2])}"

    int_findings = _find_in_findings(
        persona_findings,
        ["integratie", "interface", "middleware", "cloverleaf", "hl7"],
        persona_ids=["application", "integration", "network"],
    )
    data["roadmap_integration_fit"] = "[VERIFY]"
    data["roadmap_integration_gap"] = "[—]"
    data["roadmap_integration_rationale"] = ""
    if int_findings:
        data["roadmap_integration_rationale"] = f"[VERIFY] {'; '.join(int_findings[:2])}"

    infra_findings = _find_in_findings(
        persona_findings,
        ["infrastructuur", "server", "cloud", "network", "hosting"],
        persona_ids=["network", "application"],
    )
    data["roadmap_infra_fit"] = "[VERIFY]"
    data["roadmap_infra_gap"] = "[—]"
    data["roadmap_infra_rationale"] = ""
    if infra_findings:
        data["roadmap_infra_rationale"] = f"[VERIFY] {'; '.join(infra_findings[:2])}"

    sec_findings = _find_in_findings(
        persona_findings,
        ["security", "beveiliging", "encryptie", "firewall"],
        persona_ids=["security"],
    )
    data["roadmap_security_fit"] = "[VERIFY]"
    data["roadmap_security_gap"] = "[—]"
    data["roadmap_security_rationale"] = ""
    if sec_findings:
        data["roadmap_security_rationale"] = f"[VERIFY] {'; '.join(sec_findings[:2])}"

    data["roadmap_strategic_assessment"] = "[VERIFY]"

    if classification:
        data["roadmap_affected_items"] = [
            {
                "name": getattr(classification, "request_type", "unknown"),
                "quarter": "[VERIFY]",
                "impact_description": "[VERIFY]",
            }
        ]

    return data


# ---------------------------------------------------------------------------
# Network impact product data
# ---------------------------------------------------------------------------


def extract_network_data(
    persona_findings: list[dict],
    landscape: dict | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    net_findings = _find_in_findings(
        persona_findings,
        ["network", "netwerk", "bandwidth", "latency", "vlan", "firewall", "zone"],
        persona_ids=["network", "security"],
    )

    data["network_system_overview"] = ""
    if net_findings:
        data["network_system_overview"] = f"[VERIFY] {'; '.join(net_findings[:2])}"

    data["network_impact_level"] = ""
    if _has_keyword(persona_findings, ["network", "netwerk"], ["network"]):
        net_rating = ""
        for pf in persona_findings:
            if pf.get("perspective_id") == "network":
                net_rating = pf.get("rating", "na")
        if net_rating == "block":
            data["network_impact_level"] = "[VERIFY] Hoog — netwerkpersona geeft blokkade"
        elif net_rating == "concern":
            data["network_impact_level"] = "[VERIFY] Verhoogd — netwerkpersona heeft zorgen"

    if landscape:
        interfaces = landscape.get("relatedInterfaces", [])
        flows = []
        for intf in interfaces[:10]:
            flows.append(
                {
                    "source": intf.get("name", "[VERIFY]"),
                    "destination": "[VERIFY]",
                    "protocol": "[VERIFY]",
                    "description": intf.get("name", ""),
                    "avg_bandwidth": "[—]",
                    "peak_bandwidth": "[—]",
                    "volume_daily": "[—]",
                    "dest_port": "[ARCHITECT INPUT NEEDED]",
                    "transport": "TCP",
                    "port_notes": "[—]",
                    "qos_priority": "[—]",
                    "max_latency": "[—]",
                    "qos_rationale": "[—]",
                }
            )
        if flows:
            data["network_data_flows"] = flows

    return data


# ---------------------------------------------------------------------------
# Tech radar product data
# ---------------------------------------------------------------------------


def extract_tech_radar_data(
    persona_findings: list[dict],
    classification: Any | None = None,
    landscape: dict | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    data["tech_radar_rationale"] = ""
    app_findings = _find_in_findings(
        persona_findings,
        ["tech radar", "lifecycle", "adopt", "hold", "assess", "trial"],
        persona_ids=["application", "portfolio"],
    )
    if app_findings:
        data["tech_radar_rationale"] = f"[VERIFY] {'; '.join(app_findings[:2])}"

    if classification:
        data["tech_radar_category"] = "[VERIFY]"
        data["tech_radar_current_ring"] = "Nieuw"

    if landscape:
        status = landscape.get("techRadarStatus", "unknown")
        if status and status != "unknown":
            data["tech_radar_status"] = f"[VERIFY] Portfolio status: {status}"

    tech_conditions = _extract_conditions_for(
        persona_findings, ["tech radar", "lifecycle", "vendor", "SaaS", "eol", "end-of-life"]
    )
    if tech_conditions:
        data["tech_radar_conditions"] = tech_conditions[:5]

    return data


# ---------------------------------------------------------------------------
# Integration design product data
# ---------------------------------------------------------------------------


def extract_integration_data(
    persona_findings: list[dict],
    landscape: dict | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    int_findings = _find_in_findings(
        persona_findings,
        ["integratie", "interface", "hl7", "fhir", "api", "middleware", "cloverleaf"],
        persona_ids=["integration", "application", "network"],
    )

    data["integration_overview"] = ""
    if int_findings:
        data["integration_overview"] = f"[VERIFY] {'; '.join(int_findings[:2])}"

    data["integration_error_retry"] = "[VERIFY]"
    data["integration_error_dlq"] = "[VERIFY]"
    data["integration_error_nak"] = "[VERIFY]"
    data["integration_sla_availability"] = "[VERIFY]"
    data["integration_sla_latency"] = "[VERIFY]"

    return data


# ---------------------------------------------------------------------------
# EU AI Act product data
# ---------------------------------------------------------------------------


def extract_ai_act_data(
    persona_findings: list[dict],
    biv: dict,
    request_type: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    data["ai_unacceptable_1"] = "Nee"
    data["ai_unacceptable_2"] = "Nee"
    data["ai_unacceptable_3"] = "Nee"

    if request_type == "ai-ml" or _has_keyword(
        persona_findings, ["ai", "machine learning", "algoritme", "predict"]
    ):
        data["ai_highrisk_medical"] = "[VERIFY]"
        data["ai_highrisk_medical_rationale"] = "[VERIFY]"
        data["ai_highrisk_cds"] = "[VERIFY]"

    data["ai_ob_risk_mgmt"] = "[Onbekend]"
    data["ai_ob_data_gov"] = "[Onbekend]"
    data["ai_ob_human_oversight"] = "[Onbekend]"
    data["ai_ob_accuracy"] = "[Onbekend]"
    data["ai_ob_dpia"] = "[—]"
    data["ai_oversight_model"] = "[VERIFY]"
    data["ai_oversight_person"] = "[VERIFY]"
    data["ai_override"] = "[VERIFY]"
    data["ai_bias_demo_risk"] = "[VERIFY]"
    data["ai_bias_demo_mitigation"] = "[—]"
    data["ai_bias_auto_risk"] = "[VERIFY]"
    data["ai_bias_auto_mitigation"] = "[—]"

    if _has_keyword(persona_findings, ["bias", "vooroordel", "discriminatie"], ["fg-dpo", "cmio"]):
        data["ai_bias_demo_risk"] = "[VERIFY] Bias mentioned in persona assessment"
    if _has_keyword(persona_findings, ["human.overrid", "menselijk", "toezicht"]):
        data["ai_ob_human_oversight"] = "[VERIFY] Human oversight mentioned"

    return data


# ---------------------------------------------------------------------------
# Vendor assessment product data
# ---------------------------------------------------------------------------


def extract_vendor_data(
    persona_findings: list[dict],
    landscape: dict | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    data["vendor_financial_stability"] = "[VERIFY]"
    data["vendor_nl_references"] = "[VERIFY]"
    data["product_category"] = "[VERIFY]"
    data["product_zira_function"] = "[—]"
    data["product_landscape_overlap"] = "[VERIFY]"
    data["product_personal_data"] = "[VERIFY]"
    data["product_special_category_data"] = "[VERIFY]"
    data["tech_radar_rationale"] = "[VERIFY]"
    data["vendor_nen7510"] = "[VERIFY]"
    data["vendor_nen7512"] = "[—]"
    data["vendor_nen7513"] = "[—]"
    data["vendor_dpa"] = "[VERIFY]"
    data["vendor_hosting_eer"] = "[VERIFY]"
    data["vendor_exit_clause"] = "[VERIFY]"
    data["vendor_escrow"] = "[—]"
    data["vendor_pentest"] = "[—]"
    data["vendor_sla_availability"] = "[VERIFY]"
    data["vendor_audit_right"] = "[VERIFY]"

    if _has_keyword(persona_findings, ["patient", "patiëntdata", "persoonsgegevens"]):
        data["product_personal_data"] = "[VERIFY] Patient/personal data involved"
        data["product_special_category_data"] = "[VERIFY] Health data (Art 9 AVG)"

    return data


# ---------------------------------------------------------------------------
# Decommission checklist product data
# ---------------------------------------------------------------------------


def extract_decommission_data(
    persona_findings: list[dict],
    landscape: dict | None = None,
    request: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    data["decommission_system_name"] = request or "[VERIFY]"
    data["decommission_cmdb_id"] = "[VERIFY]"
    data["decommission_owner"] = "[VERIFY]"
    data["vendor_name"] = "[VERIFY]"
    data["decommission_upstream"] = []
    data["decommission_downstream"] = []
    data["decommission_data_sets"] = []

    if landscape:
        apps = landscape.get("existingApps", [])
        interfaces = landscape.get("relatedInterfaces", [])
        for app in apps[:5]:
            data["decommission_upstream"].append(
                {
                    "system": app.get("name", "[VERIFY]"),
                    "interface": "[VERIFY]",
                    "impact": "[VERIFY]",
                }
            )
        for intf in interfaces[:5]:
            data["decommission_downstream"].append(
                {
                    "system": intf.get("name", "[VERIFY]"),
                    "interface": "[VERIFY]",
                    "migration_plan": "[ARCHITECT INPUT NEEDED]",
                }
            )

    if _has_keyword(persona_findings, ["patient", "patiënt"]):
        data["decommission_data_sets"] = [
            {
                "name": "[VERIFY] Patiëntgegevens",
                "sensitivity": "Hoog (V≥3)",
                "destination": "[ARCHITECT INPUT NEEDED]",
                "status": "Open",
            }
        ]

    return data


# ---------------------------------------------------------------------------
# Master extraction — called from orchestrator
# ---------------------------------------------------------------------------


def extract_all_product_data(
    persona_findings: list[dict],
    biv: dict,
    classification: Any | None = None,
    landscape: dict | None = None,
    request_type: str = "",
    request: str = "",
    principetoets: list[dict] | dict | None = None,
    biv_controls: list[dict] | dict | None = None,
    language: str = "nl",
    required_documents: list[str] | None = None,
) -> dict[str, Any]:
    """Extract product-specific data from pipeline output for template filling.

    Only extracts data for documents that are actually required.
    Returns a flat dict that can be merged into build_document_context output.
    """
    required = set(required_documents or [])
    combined: dict[str, Any] = {}

    if "security-assessment" in required:
        combined.update(extract_security_data(persona_findings, biv, landscape))
    if "clinical-impact" in required:
        combined.update(extract_clinical_data(persona_findings, biv, landscape, request_type))
    if "dpia" in required:
        combined.update(extract_dpia_data(persona_findings, biv, request_type, language))
    if "bia-biv" in required:
        combined.update(extract_bia_data(persona_findings, biv, biv_controls, language))
    if "roadmap-impact" in required:
        combined.update(
            extract_roadmap_data(persona_findings, classification, landscape, principetoets)
        )
    if "network-impact" in required:
        combined.update(extract_network_data(persona_findings, landscape))
    if "tech-radar-update" in required:
        combined.update(extract_tech_radar_data(persona_findings, classification, landscape))
    if "integration-design" in required:
        combined.update(extract_integration_data(persona_findings, landscape))
    if "eu-ai-act" in required:
        combined.update(extract_ai_act_data(persona_findings, biv, request_type))
    if "vendor-assessment" in required:
        combined.update(extract_vendor_data(persona_findings, landscape))
    if "decommission-checklist" in required:
        combined.update(extract_decommission_data(persona_findings, landscape, request))

    return combined
