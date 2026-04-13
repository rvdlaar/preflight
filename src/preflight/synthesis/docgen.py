"""
Document generation — Jinja2-powered rendering of Preflight templates.

Takes pipeline output (ClassificationResult + persona findings + BIV + etc.)
and generates filled documents from the Markdown templates.

Design decisions:
- Templates use [bracket] and {{variable}} placeholders — we normalize both to Jinja2
- Context is built from PipelineResult or raw dict
- Each generated document gets the accountability disclaimer appended
- Bilingual NL/EN sections are preserved from templates
- [ARCHITECT INPUT NEEDED] markers are left for human completion
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import jinja2

from preflight.synthesis.engine import (
    ACCOUNTABILITY_DISCLAIMER,
    append_disclaimer,
    determine_required_documents,
    format_persona_findings,
    generate_risk_register,
    generate_conditions_table,
)
from preflight.pipeline.pipeline import (
    generate_principetoets,
    deduplicate_findings,
    NL_EN,
    t as translate_term,
)

TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"

RATING_NL = {
    "approve": "Akkoord",
    "conditional": "Voorwaardelijk",
    "concern": "Bezorgd",
    "block": "Blokkade",
    "na": "N.v.t.",
}

AUTHORITY_NL = {
    "VETO": "Vetorecht",
    "ESCALATION": "Escalatie",
    "INDEPENDENT": "Onafhankelijk",
    "CHALLENGE": "Aanvechtging",
    "PATIENT_SAFETY": "Patiëntveiligheid",
}


# ---------------------------------------------------------------------------
# Jinja2 environment setup
# ---------------------------------------------------------------------------


def _create_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        undefined=jinja2.Undefined,
        keep_trailing_newline=True,
    )

    env.filters["rating_nl"] = lambda r: RATING_NL.get(r, r)
    env.filters["authority_nl"] = lambda a: AUTHORITY_NL.get(a, a or "-")
    env.filters["nl_date"] = lambda d: (
        d if isinstance(d, str) else date.today().strftime("%Y-%m-%d")
    )

    return env


def _normalize_template(template_text: str) -> str:
    """Prepare template for Jinja2 rendering.

    Templates contain mixed syntax:
    - {{variable_name}} — proper Jinja2 variables (keep)
    - {{expr | filter}} — Jinja2 filter expressions (keep)
    - {% control %} — Jinja2 control structures (keep)
    - {{descriptive text with spaces}} — placeholder descriptions (escape)
    - [bracket placeholders] — convert select ones to Jinja2

    Strategy: keep valid Jinja2 expressions as-is, convert {{descriptive text}}
    to HTML comments, convert select [brackets] to {{ var }}.
    """
    _valid_var = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")

    _jinja2_expr = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.\s|()\"',:\-]*$")

    def _escape_braces(match: re.Match) -> str:
        inner = match.group(1).strip()
        if _valid_var.match(inner):
            return match.group(0)
        first_token = inner.split("|")[0].strip().split(".")[0].strip()
        dot_followed_by_space = re.search(r"[a-zA-Z]\.\s+[a-zA-Z]", inner)
        is_valid_expr = (
            _valid_var.match(first_token)
            and _jinja2_expr.match(inner)
            and not dot_followed_by_space
        )
        if is_valid_expr:
            return match.group(0)
        if inner.startswith('"') or inner.startswith("'"):
            return match.group(0)
        return f"<!-- PLACEHOLDER: {inner} -->"

    result = re.sub(r"\{\{(.+?)\}\}", _escape_braces, template_text)

    def _replace_bracket(match: re.Match) -> str:
        content = match.group(1)
        content_stripped = content.strip()

        if re.match(r"^\d+\.\d+$", content_stripped):
            return match.group(0)
        if re.match(r"^\d+$", content_stripped):
            return match.group(0)
        if "|" in content_stripped:
            return match.group(0)
        if "=" in content_stripped:
            return match.group(0)
        if len(content_stripped) < 3:
            return match.group(0)

        key_map = {
            "voorstel naam": "proposal_name",
            "naam verantwoordelijk architect": "architect_name",
            "naam, afdeling": "requestor_name_dept",
            "YYYY-MM-DD": "date",
            "Fast (batched) | Deep (panel)": "assessment_mode",
        }

        key = key_map.get(content_stripped)
        if key:
            return f"{{{{ {key} }}}}"
        return match.group(0)

    result = re.sub(r"\[([^\[\]]{3,}?)\]", _replace_bracket, result)

    return result


# ---------------------------------------------------------------------------
# Context builder — turns pipeline output into template-ready context
# ---------------------------------------------------------------------------


def build_document_context(
    proposal_name: str = "",
    request_type: str = "new-application",
    impact_level: str = "medium",
    classification: Any | None = None,
    persona_findings: list[dict] | None = None,
    ratings: dict[str, str] | None = None,
    triage: dict | None = None,
    biv: dict | None = None,
    biv_controls: dict | list[dict] | None = None,
    conditions: list[dict] | None = None,
    principetoets: dict | list[dict] | None = None,
    authority_actions: list[dict] | None = None,
    authority_summary: str = "",
    risk_register: str | None = None,
    conditions_table: str | None = None,
    citation_appendix: str | None = None,
    landscape: dict | None = None,
    zira: dict | None = None,
    assessment_mode: str = "fast",
    language: str = "nl",
    documents: dict[str, str] | None = None,
    citation_mapping: Any | None = None,
    product_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings = persona_findings or []
    ratings = ratings or {}
    triage = triage or {"treatment": "standard-review"}
    biv = biv or {"B": 2, "I": 2, "V": 2}
    biv_controls_raw = biv_controls or {}
    if isinstance(biv_controls_raw, list):
        biv_controls = {
            c.get("requirement", f"control-{i}"): c for i, c in enumerate(biv_controls_raw)
        }
    else:
        biv_controls = biv_controls_raw
    conditions = conditions or []
    principetoets_raw = principetoets or []
    if isinstance(principetoets_raw, dict):
        principetoets = principetoets_raw.get("principles", [principetoets_raw])
    else:
        principetoets = principetoets_raw
    authority_actions = authority_actions or []
    landscape = landscape or {}
    zira = zira or {}

    blocks = [f for f in findings if f.get("rating") == "block"]
    concerns = [f for f in findings if f.get("rating") == "concern"]
    conditionals = [f for f in findings if f.get("rating") == "conditional"]
    approves = [f for f in findings if f.get("rating") == "approve"]

    recommendation = "Goedkeuren met voorwaarden" if language == "nl" else "Approve with conditions"
    if blocks:
        recommendation = "Afwijzen" if language == "nl" else "Reject"
    elif not concerns and not blocks:
        if conditionals:
            recommendation = (
                "Goedkeuren met voorwaarden" if language == "nl" else "Approve with conditions"
            )
        else:
            recommendation = "Goedkeuren" if language == "nl" else "Approve"

    veto_actions = [a for a in authority_actions if a.get("type") == "VETO"]
    escalation_actions = [a for a in authority_actions if a.get("type") == "ESCALATION"]
    fg_actions = [a for a in authority_actions if a.get("type") == "INDEPENDENT"]

    board_time = "15 min"
    if len(findings) > 10 or blocks:
        board_time = "volledige sessie"
    elif concerns:
        board_time = "30 min"

    status = "DRAFT"
    if triage.get("treatment") == "deep-review":
        status = "ARCHITECT_REVIEWED"

    today = date.today().strftime("%Y-%m-%d")

    biv_rpo = biv_controls.get("RPO", "24u" if biv.get("B", 2) >= 3 else "72u")
    biv_rto = biv_controls.get("RTO", "4u" if biv.get("B", 2) >= 3 else "24u")

    ctx = {
        "proposal_name": proposal_name or "(naam voorstel)",
        "date": today,
        "version": "0.1",
        "status": status,
        "architect_name": "(architect)",
        "requestor_name": "(aanvrager)",
        "requestor_name_dept": "(naam, afdeling)",
        "assessment_mode": "Fast (batched)" if assessment_mode == "fast" else "Deep (panel)",
        "biv_classification": f"B={biv.get('B', '?')} I={biv.get('I', '?')} V={biv.get('V', '?')}",
        "biv_b": biv.get("B", "?"),
        "biv_i": biv.get("I", "?"),
        "biv_v": biv.get("V", "?"),
        "biv_rpo": biv_rpo,
        "biv_rto": biv_rto,
        "request_type": request_type,
        "impact_level": impact_level,
        "recommendation": recommendation,
        "board_time": board_time,
        "language": language,
        "triage_treatment": translate_term(triage.get("treatment", "standard-review"), language),
        "triage_reason": triage.get("reason", ""),
        "persona_findings": findings,
        "persona_findings_formatted": format_persona_findings(findings),
        "ratings": ratings,
        "blocks_count": len(blocks),
        "concerns_count": len(concerns),
        "conditionals_count": len(conditionals),
        "approves_count": len(approves),
        "authority_actions": authority_actions,
        "authority_summary": authority_summary,
        "veto_exercised": f"Ja — door {', '.join(a.get('persona', 'onbekend') for a in veto_actions)}"
        if veto_actions
        else "Nee",
        "escalation": f"Ja — door {', '.join(a.get('persona', 'onbekend') for a in escalation_actions)}"
        if escalation_actions
        else "Nee",
        "fg_determination": f"Concept — bevestiging door FG vereist: {'; '.join(a.get('finding', '')[:80] for a in fg_actions)}"
        if fg_actions
        else "N.v.t.",
        "biv_controls": biv_controls,
        "biv_full": biv,
        "conditions": conditions,
        "conditions_table": conditions_table or generate_conditions_table(findings),
        "risk_register": risk_register or generate_risk_register(findings),
        "principetoets": principetoets,
        "deduplicated_findings": deduplicate_findings(findings),
        "citation_appendix": citation_appendix or "",
        "disclaimer": ACCOUNTABILITY_DISCLAIMER,
        "landscape": landscape,
        "zira": zira,
        "classification": classification,
        "citation_mapping": citation_mapping,
        "existing_apps": landscape.get("existingApps", []),
        "related_interfaces": landscape.get("relatedInterfaces", []),
        "open_risks": landscape.get("openRisks", []),
        "tech_radar_status": landscape.get("techRadarStatus", "unknown"),
        "capability_map": landscape.get("capabilityMap", "not found"),
        "psa_id": f"PSA-{today.replace('-', '')}",
        "adr_number": "",
        "adr_context": "",
        "adr_drivers": [],
        "adr_options": [],
        "adr_chosen_option": "",
        "adr_rationale": "",
        "adr_consequences_good": [],
        "adr_consequences_bad": [],
        "adr_related_decisions": [],
        "dpia_fg_name": "",
        "dpia_data_categories": [],
        "dpia_data_subjects": [],
        "dpia_art6_bases": [],
        "dpia_art9_bases": [],
        "dpia_retention": [],
        "dpia_recipients": [],
        "bia_affected_processes": [],
        "bia_upstream_deps": [],
        "bia_downstream_deps": [],
        "bia_assessor_disagreements": [],
        "nen7510_controls": [],
        "stride_threats": [],
        "clinical_workflows": [],
        "clinical_departments": "",
        "integration_flows": [],
        "integration_message_specs": [],
        "integration_cascade_relations": [],
        "network_data_flows": [],
        "network_zone_placement": [],
        "network_firewall_rules": [],
        "network_impact_level": "",
        "process_affected": [],
        "process_as_is_steps": [],
        "process_to_be_steps": [],
        "process_handovers": [],
        "process_exceptions": [],
        "process_impact_level": "",
        "vendor_name": "",
        "vendor_country": "",
        "vendor_existing": "",
        "product_name": "",
        "product_hosting": "",
        "tech_radar_name": "",
        "tech_radar_category": "",
        "tech_radar_current_ring": "",
        "tech_radar_conditions": [],
        "roadmap_affected_items": [],
        "roadmap_blocked_items": [],
        "roadmap_unblocked_items": [],
        "roadmap_conflicts": [],
        "roadmap_capability_gaps": [],
        "roadmap_strategic_assessment": "",
        "decommission_system_name": "",
        "decommission_cmdb_id": "",
        "decommission_owner": "",
        "decommission_upstream": [],
        "decommission_downstream": [],
        "decommission_data_sets": [],
        "ai_system_name": "",
        "ai_type": "",
        "ai_intended_purpose": "",
        "ai_autonomy": "",
        "ai_risk_tier": "",
    }

    if product_data:
        for k, v in product_data.items():
            if k in ctx:
                ctx[k] = v

    return ctx


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

_env = None


def _get_env() -> jinja2.Environment:
    global _env
    if _env is None:
        _env = _create_env()
    return _env


def render_template(template_name: str, context: dict[str, Any]) -> str:
    env = _get_env()
    template_path = f"{template_name}.md"
    try:
        raw = env.loader.get_source(env, template_path)[0]
    except jinja2.TemplateNotFound:
        return f"[Template not found: {template_path}]"

    normalized = _normalize_template(raw)
    template = env.from_string(normalized)

    try:
        rendered = template.render(**context)
    except Exception as e:
        rendered = f"[Error rendering {template_name}: {e}]\n\n{raw}"

    rendered = append_disclaimer(rendered)

    return rendered


def render_all_documents(context: dict[str, Any]) -> dict[str, str]:
    request_type = context.get("request_type", "new-application")
    ratings = context.get("ratings", {})
    biv = context.get("biv_full", context.get("biv", {}))

    required = determine_required_documents(request_type, ratings, biv)

    documents: dict[str, str] = {}
    for name in required:
        try:
            documents[name] = render_template(name, context)
        except Exception as e:
            documents[name] = f"[Error rendering {name}: {e}]"

    citation_mapping = context.get("citation_mapping")
    from preflight.citation.processor import CitationProcessor, CitationMode

    mode = CitationMode.HYPERLINK if citation_mapping else CitationMode.REMOVE
    proc = CitationProcessor(mode=mode)
    if citation_mapping:
        proc.mapping.merge(citation_mapping)

    processed: dict[str, str] = {}
    for doc_name, doc_text in documents.items():
        text, _ = proc.process(doc_text)
        if citation_mapping and doc_name in ("psa", "adr"):
            refs = proc.format_references()
            if refs:
                text = f"{text}\n\n---\n\n{refs}"
        processed[doc_name] = text
    documents = processed

    return documents


# ---------------------------------------------------------------------------
# Convenience: render from PipelineResult
# ---------------------------------------------------------------------------


def render_from_pipeline_result(result: Any) -> dict[str, str]:
    from preflight.pipeline.orchestrator import PipelineResult

    if not isinstance(result, PipelineResult):
        raise TypeError(f"Expected PipelineResult, got {type(result)}")

    cls = result.classification
    context = build_document_context(
        proposal_name=cls.summary_en if cls else "",
        request_type=cls.request_type if cls else "new-application",
        impact_level=cls.impact_level if cls else "medium",
        classification=cls,
        persona_findings=result.persona_findings,
        ratings={},
        triage=result.triage,
        biv=result.biv,
        biv_controls=result.biv_controls,
        conditions=result.conditions,
        principetoets=result.principetoets,
        authority_actions=result.authority_actions,
        risk_register=result.risk_register if isinstance(result.risk_register, str) else "",
        conditions_table="",
        citation_appendix=result.citation_appendix,
    )

    return render_all_documents(context)
