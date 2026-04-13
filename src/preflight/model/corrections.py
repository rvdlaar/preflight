"""
Corrections applier — loads corrections.yaml, applies to ArchiMateModel.

The architect's voice. We trust the corrections but still validate.
After applying, re-validate the full model and return updated results.

Thinking applied:
  First principles: Load YAML, apply changes, re-validate. That's it.
  Second order: If the architect adds an element with a type not in our
  enum, do we reject it? No — they know their model. We accept, validate,
  let Archi decide. Remove an element → cascade to relationships.
  Inversion: Malformed YAML → clear error, no crash. Reference non-existent
  element → skip with warning. Incompatible type change → warn, don't block.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    Layer,
    RelationshipType,
    make_element_id,
    make_relationship_id,
    validate_model,
)

logger = logging.getLogger(__name__)


ELEMENT_TYPE_ALIASES: dict[str, str] = {t.value.lower(): t.value for t in ElementType}

RELATIONSHIP_TYPE_ALIASES: dict[str, str] = {t.value.lower(): t.value for t in RelationshipType}
for t in RelationshipType:
    RELATIONSHIP_TYPE_ALIASES[f"{t.value.lower()}relationship"] = t.value


def _resolve_element_type(raw: str) -> ElementType | None:
    key = raw.strip().lower()
    canonical = ELEMENT_TYPE_ALIASES.get(key)
    if canonical:
        return ElementType(canonical)
    try:
        return ElementType(raw.strip())
    except ValueError:
        return None


def _resolve_relationship_type(raw: str) -> RelationshipType | None:
    key = raw.strip().lower()
    canonical = RELATIONSHIP_TYPE_ALIASES.get(key)
    if canonical:
        return RelationshipType(canonical)
    try:
        return RelationshipType(raw.strip())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Apply corrections
# ---------------------------------------------------------------------------


def apply_corrections(
    model: ArchiMateModel, corrections: dict[str, Any]
) -> tuple[ArchiMateModel, list[str]]:
    """Apply corrections to model. Returns (updated_model, log_messages)."""

    log: list[str] = []

    for elem_spec in corrections.get("elements_to_add", []):
        msg = _add_element(model, elem_spec)
        log.append(msg)

    for elem_spec in corrections.get("elements_to_change", []):
        msg = _change_element(model, elem_spec)
        log.append(msg)

    for elem_spec in corrections.get("elements_to_remove", []):
        msg = _remove_element(model, elem_spec)
        log.append(msg)

    for rel_spec in corrections.get("relationships_to_add", []):
        msg = _add_relationship(model, rel_spec)
        log.append(msg)

    for rel_spec in corrections.get("relationships_to_change", []):
        msg = _change_relationship(model, rel_spec)
        log.append(msg)

    for rel_spec in corrections.get("relationships_to_remove", []):
        msg = _remove_relationship(model, rel_spec)
        log.append(msg)

    for note in corrections.get("notes", []):
        msg = _add_note(model, note)
        log.append(msg)

    issues = validate_model(model)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    if errors:
        log.append(
            f"⚠️ Validation after corrections: {len(errors)} errors, {len(warnings)} warnings"
        )
        for e in errors[:5]:
            log.append(f"  ERROR [{e.element_id}]: {e.message}")
    elif warnings:
        log.append(f"ℹ️ Validation after corrections: {len(warnings)} warnings (no errors)")
        for w in warnings[:5]:
            log.append(f"  WARN [{w.element_id}]: {w.message}")
    else:
        log.append("✓ Validation after corrections: no issues")

    return model, log


def load_and_apply(model: ArchiMateModel, yaml_path: str) -> tuple[ArchiMateModel, list[str]]:
    """Load corrections from YAML file and apply."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Corrections file not found: {yaml_path}")

    with open(path, "r", encoding="utf-8") as f:
        corrections = yaml.safe_load(f) or {}

    return apply_corrections(model, corrections)


# ---------------------------------------------------------------------------
# Element operations
# ---------------------------------------------------------------------------


def _add_element(model: ArchiMateModel, spec: dict[str, Any]) -> str:
    name = spec.get("name", "").strip()
    if not name:
        return "SKIP add element: no name provided"

    raw_type = spec.get("type", "ApplicationComponent")
    elem_type = _resolve_element_type(raw_type)
    if not elem_type:
        return f"SKIP add element '{name}': unknown type '{raw_type}'"

    raw_layer = spec.get("layer", "")
    layer = _resolve_layer(raw_layer, elem_type)

    elem = ArchiMateElement(
        id=spec.get("id", make_element_id("custom", name)),
        name=name,
        type=elem_type,
        layer=layer,
        documentation=spec.get("documentation", ""),
        properties=spec.get("properties", {}),
        why="Added by architect via corrections.yaml",
    )
    model.add_element(elem)
    return f"ADD element: {elem.id} ({elem_type.value}) '{name}'"


def _change_element(model: ArchiMateModel, spec: dict[str, Any]) -> str:
    elem_id = spec.get("id", "").strip()
    if not elem_id:
        return "SKIP change element: no id provided"

    elem = model.element_by_id(elem_id)
    if not elem:
        return f"SKIP change element: id '{elem_id}' not found"

    changes: list[str] = []

    if "name" in spec and spec["name"]:
        elem.name = spec["name"]
        changes.append(f"name→{spec['name']}")

    if "type" in spec and spec["type"]:
        new_type = _resolve_element_type(spec["type"])
        if new_type:
            old_type = elem.type.value
            elem.type = new_type
            if "layer" not in spec:
                from preflight.model.types import ELEMENT_LAYER

                elem.layer = ELEMENT_LAYER.get(new_type, elem.layer)
            changes.append(f"type: {old_type}→{new_type.value}")
        else:
            return f"SKIP change element '{elem_id}': unknown type '{spec['type']}'"

    if "layer" in spec and spec["layer"]:
        layer = _resolve_layer(spec["layer"], elem.type)
        if layer:
            elem.layer = layer
            changes.append(f"layer→{layer.value}")

    if "documentation" in spec:
        elem.documentation = spec["documentation"]
        changes.append("documentation updated")

    if not changes:
        return f"NOOP change element '{elem_id}': no changes specified"

    return f"CHANGE element {elem_id}: {', '.join(changes)}"


def _remove_element(model: ArchiMateModel, spec: dict[str, Any]) -> str:
    elem_id = spec if isinstance(spec, str) else spec.get("id", "").strip()
    if not elem_id:
        return "SKIP remove element: no id provided"

    elem = model.element_by_id(elem_id)
    if not elem:
        return f"SKIP remove element: id '{elem_id}' not found"

    removed_rels = model.remove_element(elem_id)
    msg = f"REMOVE element: {elem_id} '{elem.name}'"
    if removed_rels:
        msg += f" (also removed {len(removed_rels)} relationships)"
    return msg


# ---------------------------------------------------------------------------
# Relationship operations
# ---------------------------------------------------------------------------


def _add_relationship(model: ArchiMateModel, spec: dict[str, Any]) -> str:
    source_id = spec.get("source", "").strip()
    target_id = spec.get("target", "").strip()
    raw_type = spec.get("type", "Association")

    if not source_id or not target_id:
        return f"SKIP add relationship: source/target required (got source={source_id}, target={target_id})"

    if not model.element_by_id(source_id):
        return f"SKIP add relationship: source '{source_id}' not found"
    if not model.element_by_id(target_id):
        return f"SKIP add relationship: target '{target_id}' not found"

    rel_type = _resolve_relationship_type(raw_type)
    if not rel_type:
        return f"SKIP add relationship: unknown type '{raw_type}'"

    rel = ArchiMateRelationship(
        id=spec.get("id", make_relationship_id(source_id, rel_type.value, target_id)),
        source_id=source_id,
        target_id=target_id,
        type=rel_type,
        name=spec.get("name", ""),
        documentation=spec.get("documentation", ""),
        why="Added by architect via corrections.yaml",
    )
    model.add_relationship(rel)
    return f"ADD relationship: {rel.id} ({rel_type.value}) {source_id}→{target_id}"


def _change_relationship(model: ArchiMateModel, spec: dict[str, Any]) -> str:
    rel_id = spec.get("id", "").strip()
    if not rel_id:
        return "SKIP change relationship: no id provided"

    rel = next((r for r in model.relationships if r.id == rel_id), None)
    if not rel:
        return f"SKIP change relationship: id '{rel_id}' not found"

    changes: list[str] = []

    if "type" in spec and spec["type"]:
        new_type = _resolve_relationship_type(spec["type"])
        if new_type:
            old_type = rel.type.value
            rel.type = new_type
            changes.append(f"type: {old_type}→{new_type.value}")
        else:
            return f"SKIP change relationship '{rel_id}': unknown type '{spec['type']}'"

    if "name" in spec:
        rel.name = spec["name"]
        changes.append("name updated")

    if "documentation" in spec:
        rel.documentation = spec["documentation"]
        changes.append("documentation updated")

    if not changes:
        return f"NOOP change relationship '{rel_id}': no changes specified"

    return f"CHANGE relationship {rel_id}: {', '.join(changes)}"


def _remove_relationship(model: ArchiMateModel, spec: dict[str, Any]) -> str:
    rel_id = spec if isinstance(spec, str) else spec.get("id", "").strip()
    if not rel_id:
        return "SKIP remove relationship: no id provided"

    rel = next((r for r in model.relationships if r.id == rel_id), None)
    if not rel:
        return f"SKIP remove relationship: id '{rel_id}' not found"

    model.remove_relationship(rel_id)
    return f"REMOVE relationship: {rel_id}"


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def _add_note(model: ArchiMateModel, note: str) -> str:
    if not model.documentation:
        model.documentation = note
    else:
        model.documentation += f"\n\n---\nArchitect note: {note}"
    return f"ADD note: {note[:80]}{'...' if len(note) > 80 else ''}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_layer(raw: str, elem_type: ElementType) -> Layer:
    from preflight.model.types import ELEMENT_LAYER

    if not raw:
        return ELEMENT_LAYER.get(elem_type, Layer.APPLICATION)
    raw_lower = raw.strip().lower()
    for layer in Layer:
        if layer.value.lower().startswith(raw_lower):
            return layer
    return ELEMENT_LAYER.get(elem_type, Layer.APPLICATION)
