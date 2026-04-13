"""
Model builder — maps PipelineResult → ArchiMateModel.

Pure code, no LLM. Deterministic extraction rules.
Every element carries a 'why' field tracing to pipeline data.

Thinking applied:
  First principles: The builder is a pure function. Pipeline data in,
  ArchiMate model out. No hallucination. No invention. If the pipeline
  didn't produce it, the model doesn't contain it.
  Second order: Incomplete pipeline data → sparse model. That's honest.
  Missing data = missing elements, not hallucinated ones.
  The corrections.yaml is where the architect fills gaps.
  Inversion: What makes the builder produce garbage? Mapping pipeline
  data to wrong ArchiMate types. We pick reasonable defaults, document
  why, and the architect corrects in the review step.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    Layer,
    RelationshipType,
    make_element_id,
    make_relationship_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification → element type mapping
# ---------------------------------------------------------------------------


REQUEST_TYPE_ELEMENT: dict[str, ElementType] = {
    "new-application": ElementType.APPLICATION_COMPONENT,
    "clinical-system": ElementType.APPLICATION_COMPONENT,
    "patient-data": ElementType.APPLICATION_COMPONENT,
    "integration": ElementType.APPLICATION_SERVICE,
    "infrastructure-change": ElementType.NODE,
    "decommission": ElementType.APPLICATION_COMPONENT,
    "vendor-selection": ElementType.APPLICATION_COMPONENT,
}


def _element_type_for_request(request_type: str) -> ElementType:
    return REQUEST_TYPE_ELEMENT.get(request_type, ElementType.APPLICATION_COMPONENT)


# ---------------------------------------------------------------------------
# Helper extractors — pull structured data from PipelineResult
# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_model(result: Any) -> ArchiMateModel:
    """Build an ArchiMateModel from a PipelineResult.

    Extraction rules are deterministic:
    - proposed system → ApplicationComponent (or type from classification)
    - existing apps (landscape) → ApplicationComponent
    - ZiRA business functions → BusinessFunction
    - ZiRA information domains → BusinessObject / DataObject
    - BIV controls (B/I/V ≥ 2) → Requirement
    - conditions from personas → Requirement or Constraint
    - authority actions (VETO, ESCALATION) → Assessment
    - relationships derived from context (integration, ZiRA, BIV)

    Every element and relationship gets a 'why' field.
    """
    cls = result.classification
    request_type = cls.request_type if cls else "new-application"
    impact_level = cls.impact_level if cls else "medium"
    request_text = ""
    if cls and hasattr(cls, "summary_en") and cls.summary_en:
        request_text = cls.summary_en
    elif hasattr(result, "documents") and result.documents:
        first_doc = next(iter(result.documents.values()), "")
        if first_doc:
            request_text = first_doc[:200]

    proposal_name = request_text or "Proposed System"

    model = ArchiMateModel(
        name=f"Preflight — {proposal_name}",
        documentation=f"Auto-generated ArchiMate model from Preflight assessment.\n"
        f"PSA ID: {result.id}\n"
        f"Classification: {request_type} / {impact_level}\n"
        f"Review this model before importing into your architecture tool.",
        psa_id=result.id,
        language=getattr(result, "language", "nl"),
    )

    _add_proposed_element(model, result, request_type, proposal_name)
    _add_landscape_elements(model, result)
    _add_zira_elements(model, result)
    _add_biv_elements(model, result)
    _add_condition_elements(model, result)
    _add_authority_elements(model, result)
    _add_relationships(model, result)

    return model


# ---------------------------------------------------------------------------
# Element extraction
# ---------------------------------------------------------------------------


def _add_proposed_element(
    model: ArchiMateModel,
    result: Any,
    request_type: str,
    proposal_name: str,
) -> None:
    elem_type = _element_type_for_request(request_type)
    elem = ArchiMateElement(
        id=make_element_id("proposed", proposal_name),
        name=proposal_name,
        type=elem_type,
        documentation=f"Proposed system from assessment {result.id}",
        properties={
            "preflight:classification": request_type,
            "preflight:impact_level": getattr(result.classification, "impact_level", "medium")
            if result.classification
            else "medium",
        },
        why=f"Pipeline classified as {request_type}",
    )
    model.add_element(elem)


def _add_landscape_elements(model: ArchiMateModel, result: Any) -> None:
    existing_apps = _extract_existing_apps(result)
    for app in existing_apps:
        app_name = app if isinstance(app, str) else app.get("name", str(app))
        elem = ArchiMateElement(
            id=make_element_id("app", app_name),
            name=app_name,
            type=ElementType.APPLICATION_COMPONENT,
            properties=_app_properties(app),
            why="Landscape context — existing application",
        )
        model.add_element(elem)

    interfaces = _extract_interfaces(result)
    for intf in interfaces:
        intf_name = intf if isinstance(intf, str) else intf.get("name", str(intf))
        elem = ArchiMateElement(
            id=make_element_id("intf", intf_name),
            name=intf_name,
            type=ElementType.APPLICATION_SERVICE,
            layer=Layer.TECHNOLOGY,
            why="Integration context — landscape interface",
        )
        model.add_element(elem)


def _add_zira_elements(model: ArchiMateModel, result: Any) -> None:
    zira = _extract_zira(result)

    if zira.get("domain"):
        elem = ArchiMateElement(
            id=make_element_id("zira", zira["domain"]),
            name=zira["domain"],
            type=ElementType.BUSINESS_FUNCTION,
            properties={"preflight:zira_domain": "primary"},
            why="ZiRA primary business domain",
        )
        model.add_element(elem)

    for bf in zira.get("businessFunctions", []):
        bf_name = bf if isinstance(bf, str) else bf.get("name", str(bf))
        elem = ArchiMateElement(
            id=make_element_id("bf", bf_name),
            name=bf_name,
            type=ElementType.BUSINESS_FUNCTION,
            why="ZiRA business function mapping",
        )
        model.add_element(elem)

    for idom in zira.get("informationDomains", []):
        idom_name = idom if isinstance(idom, str) else idom.get("name", str(idom))
        elem = ArchiMateElement(
            id=make_element_id("info", idom_name),
            name=idom_name,
            type=ElementType.BUSINESS_OBJECT,
            why="ZiRA information domain",
        )
        model.add_element(elem)

    principles = getattr(result, "principetoets", None)
    if isinstance(principles, dict):
        for p in principles.get("principles", []):
            assessment = p.get("assessment", "")
            if assessment in ("Niet", "Deels"):
                elem = ArchiMateElement(
                    id=make_element_id("princ", str(p.get("number", 0))),
                    name=f"ZiRA {p.get('number', '?')}: {p.get('name', '')}",
                    type=ElementType.PRINCIPLE,
                    documentation=p.get("definition", ""),
                    properties={"preflight:assessment": assessment},
                    why=f"ZiRA principetoets — {assessment}",
                )
                model.add_element(elem)


def _add_biv_elements(model: ArchiMateModel, result: Any) -> None:
    biv = getattr(result, "biv", {}) or {}
    if not biv:
        return

    b, i, v = biv.get("B", 0), biv.get("I", 0), biv.get("V", 0)

    if b >= 2:
        elem = ArchiMateElement(
            id="id_biv_b",
            name=f"Beschikbaarheid B={b} (RPO {biv.get('rpo', '?')}, RTO {biv.get('rto', '?')})",
            type=ElementType.REQUIREMENT,
            documentation=f"BIV availability level {b}. "
            f"RPO: {biv.get('rpo', '?')}, RTO: {biv.get('rto', '?')}.",
            properties={"preflight:biv": f"B={b}"},
            why=f"BIV analysis — B={b}",
        )
        model.add_element(elem)

    if i >= 2:
        elem = ArchiMateElement(
            id="id_biv_i",
            name=f"Integriteit I={i}",
            type=ElementType.REQUIREMENT,
            properties={"preflight:biv": f"I={i}"},
            why=f"BIV analysis — I={i}",
        )
        model.add_element(elem)

    if v >= 2:
        elem = ArchiMateElement(
            id="id_biv_v",
            name=f"Vertrouwelijkheid V={v}",
            type=ElementType.REQUIREMENT,
            properties={"preflight:biv": f"V={v}"},
            why=f"BIV analysis — V={v}",
        )
        model.add_element(elem)

    controls = getattr(result, "biv_controls", []) or []
    if isinstance(controls, dict):
        controls = list(controls.values())
    for idx, ctrl in enumerate(controls[:10]):
        req_text = ctrl.get("requirement", f"BIV control {idx}")
        standard = ctrl.get("standard", "")
        elem = ArchiMateElement(
            id=make_element_id("ctrl", f"{standard}_{idx}"),
            name=f"[{standard}] {req_text}",
            type=ElementType.REQUIREMENT,
            documentation=f"Standard: {standard}. Reference: {ctrl.get('reference', '')}",
            properties={
                "preflight:standard": standard,
                "preflight:reference": ctrl.get("reference", ""),
            },
            why=f"BIV control — {ctrl.get('reference', standard)}",
        )
        model.add_element(elem)


def _add_condition_elements(model: ArchiMateModel, result: Any) -> None:
    conditions = getattr(result, "conditions", []) or []
    for idx, cond in enumerate(conditions):
        cond_text = (
            cond
            if isinstance(cond, str)
            else cond.get("condition_text", cond.get("condition", str(cond)))
        )
        if not cond_text or not cond_text.strip():
            continue
        source_persona = (
            cond.get("source_persona", "pipeline") if isinstance(cond, dict) else "pipeline"
        )
        elem_type = (
            ElementType.CONSTRAINT
            if "must" in cond_text.lower() or "mag niet" in cond_text.lower()
            else ElementType.REQUIREMENT
        )
        elem = ArchiMateElement(
            id=make_element_id("cond", f"{idx}"),
            name=cond_text[:120],
            type=elem_type,
            properties={"preflight:source_persona": source_persona},
            why=f"Condition from {source_persona}",
        )
        model.add_element(elem)


def _add_authority_elements(model: ArchiMateModel, result: Any) -> None:
    authority_actions = getattr(result, "authority_actions", []) or []
    for idx, action in enumerate(authority_actions):
        if not action.get("triggered"):
            continue
        action_type = action.get("type", "")
        persona = action.get("persona", "unknown")
        findings = action.get("findings", [])
        finding_text = findings[0] if findings and isinstance(findings[0], str) else ""
        elem = ArchiMateElement(
            id=make_element_id("auth", f"{persona}_{idx}"),
            name=f"{action_type}: {persona}",
            type=ElementType.ASSESSMENT,
            documentation=finding_text[:500] if finding_text else "",
            properties={
                "preflight:authority_type": action_type,
                "preflight:persona": persona,
            },
            why=f"Authority action — {action_type} by {persona}",
        )
        model.add_element(elem)


# ---------------------------------------------------------------------------
# Relationship extraction
# ---------------------------------------------------------------------------


def _add_relationships(model: ArchiMateModel, result: Any) -> None:
    proposed = next((e for e in model.elements if e.id.startswith("id_proposed_")), None)
    if not proposed:
        return

    zira_domain = next(
        (e for e in model.elements if e.id == make_element_id("zira", _get_zira_domain(result))),
        None,
    )
    zira_bfs = [e for e in model.elements if e.id.startswith("id_bf_")]
    existing_apps = [e for e in model.elements if e.id.startswith("id_app_")]
    biv_elems = [
        e for e in model.elements if e.id.startswith("id_biv_") or e.id.startswith("id_ctrl_")
    ]
    cond_elems = [e for e in model.elements if e.id.startswith("id_cond_")]
    auth_elems = [e for e in model.elements if e.id.startswith("id_auth_")]

    for bf in zira_bfs:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Serving", bf.id),
            source_id=proposed.id,
            target_id=bf.id,
            type=RelationshipType.SERVING,
            why="ZiRA positioning — proposed system serves this business function",
        )
        model.add_relationship(rel)

    if zira_domain and zira_bfs:
        for bf in zira_bfs:
            rel = ArchiMateRelationship(
                id=make_relationship_id(bf.id, "Composition", zira_domain.id),
                source_id=zira_domain.id,
                target_id=bf.id,
                type=RelationshipType.COMPOSITION,
                why="ZiRA business function belongs to domain",
            )
            model.add_relationship(rel)

    interfaces = [e for e in model.elements if e.id.startswith("id_intf_")]
    for app in existing_apps:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Flow", app.id),
            source_id=proposed.id,
            target_id=app.id,
            type=RelationshipType.FLOW,
            why="Integration context — data flow between systems",
        )
        model.add_relationship(rel)

    for intf in interfaces:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Serving", intf.id),
            source_id=proposed.id,
            target_id=intf.id,
            type=RelationshipType.SERVING,
            why="Integration context — proposed uses this interface/service",
        )
        model.add_relationship(rel)

    for biv_elem in biv_elems:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Realization", biv_elem.id),
            source_id=proposed.id,
            target_id=biv_elem.id,
            type=RelationshipType.REALIZATION,
            why="BIV/controls — proposed system must realize this requirement",
        )
        model.add_relationship(rel)

    for cond_elem in cond_elems:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Realization", cond_elem.id),
            source_id=proposed.id,
            target_id=cond_elem.id,
            type=RelationshipType.REALIZATION,
            why="Condition — proposed system must meet this condition",
        )
        model.add_relationship(rel)

    for auth_elem in auth_elems:
        rel = ArchiMateRelationship(
            id=make_relationship_id(auth_elem.id, "Influence", proposed.id),
            source_id=auth_elem.id,
            target_id=proposed.id,
            type=RelationshipType.INFLUENCE,
            influence_modifier="--",
            why=f"Authority assessment influences proposed system",
        )
        model.add_relationship(rel)

    for info_dom in [e for e in model.elements if e.id.startswith("id_info_")]:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Access", info_dom.id),
            source_id=proposed.id,
            target_id=info_dom.id,
            type=RelationshipType.ACCESS,
            why="ZiRA — proposed system accesses this information domain",
        )
        model.add_relationship(rel)

    for princ_elem in [e for e in model.elements if e.id.startswith("id_princ_")]:
        rel = ArchiMateRelationship(
            id=make_relationship_id(proposed.id, "Realization", princ_elem.id),
            source_id=proposed.id,
            target_id=princ_elem.id,
            type=RelationshipType.REALIZATION,
            why="ZiRA principetoets — proposed system should realize this principle",
        )
        model.add_relationship(rel)


# ---------------------------------------------------------------------------
# Helper extractors — pull structured data from PipelineResult
# ---------------------------------------------------------------------------


def _extract_existing_apps(result: Any) -> list:
    landscape = _get_landscape(result)
    apps = landscape.get("existingApps", [])
    if apps:
        return apps
    if isinstance(landscape.get("raw"), dict):
        return landscape["raw"].get("existingApps", [])
    return []


def _extract_interfaces(result: Any) -> list:
    landscape = _get_landscape(result)
    if isinstance(landscape.get("raw"), dict):
        return landscape["raw"].get("interfaces", [])
    return landscape.get("relatedInterfaces", [])


def _extract_zira(result: Any) -> dict:
    principetoets = getattr(result, "principetoets", None)
    if isinstance(principetoets, dict):
        return principetoets
    return {}


def _get_zira_domain(result: Any) -> str:
    zira = _extract_zira(result)
    return zira.get("domain", "Zorg")


def _get_landscape(result: Any) -> dict:
    for attr in ("persona_contexts",):
        contexts = getattr(result, attr, None)
        if contexts:
            for ctx in contexts:
                if hasattr(ctx, "landscape") and ctx.landscape:
                    return ctx.landscape
    return {}


def _app_properties(app: Any) -> dict[str, str]:
    if isinstance(app, str):
        return {}
    props = {}
    for key in ("status", "overlap", "relation"):
        val = app.get(key)
        if val:
            props[f"preflight:{key}"] = str(val)
    return props
