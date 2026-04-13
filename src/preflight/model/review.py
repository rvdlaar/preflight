"""
Model review generator — Markdown + corrections template.

Produces a human-readable review document that the architect can
inspect before the .archimate file is generated. No tool required —
just a Markdown renderer (browser, VS Code, Obsidian).

Thinking applied:
  First principles: The review must be readable without any tool.
  Tables for scanability. Mermaid for visual context. Corrections
  template for actionability. Understand in 60 seconds.
  Second order: If the review is too long, nobody reads it. If too
  short, they can't verify. Solution: "Why" column on every row.
  Mermaid is a quick visual, not the full model.
  Inversion: What if the architect never opens corrections.yaml?
  The .archimate must be useful straight out of the pipeline. The
  review is a courtesy, not a gate.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    RelationshipType,
    validate_model,
)


# ---------------------------------------------------------------------------
# Arrow labels for relationship types
# ---------------------------------------------------------------------------

REL_ARROWS: dict[RelationshipType, str] = {
    RelationshipType.COMPOSITION: "--◆→",
    RelationshipType.AGGREGATION: "--◇→",
    RelationshipType.ASSIGNMENT: "--●→",
    RelationshipType.REALIZATION: "- -▷",
    RelationshipType.SERVING: "--▷",
    RelationshipType.ACCESS: "- -→",
    RelationshipType.INFLUENCE: "- -→",
    RelationshipType.TRIGGERING: "--▶",
    RelationshipType.FLOW: "--→",
    RelationshipType.SPECIALIZATION: "--▷▷",
    RelationshipType.ASSOCIATION: "--→",
}


def _rel_arrow(rel: ArchiMateRelationship) -> str:
    return REL_ARROWS.get(rel.type, "--→")


# ---------------------------------------------------------------------------
# Mermaid generation from model
# ---------------------------------------------------------------------------


def model_to_mermaid(model: ArchiMateModel) -> str:
    lines = ["graph TD"]
    for elem in model.elements:
        safe = _mermaid_id(elem.id)
        layer_tag = elem.layer.value if elem.layer else "?"
        type_tag = elem.type.value
        lines.append(f'    {safe}["{elem.name}<br/><small>{type_tag}</small>"]')
        lines.append(f"    style {safe} fill:{_layer_color(elem.layer)},stroke:#333")

    for rel in model.relationships:
        src = _mermaid_id(rel.source_id)
        tgt = _mermaid_id(rel.target_id)
        arrow = (
            "-.->"
            if rel.type
            in (RelationshipType.REALIZATION, RelationshipType.INFLUENCE, RelationshipType.ACCESS)
            else "-->"
        )
        label = f"|{rel.type.value}|" if rel.type != RelationshipType.ASSOCIATION else ""
        lines.append(f"    {src} {arrow} {label} {tgt}")

    return "\n".join(lines)


def _mermaid_id(id_str: str) -> str:
    import re

    return re.sub(r"[^a-zA-Z0-9]", "_", id_str)


def _layer_color(layer: Any) -> str:
    colors = {
        "Business": "#ffffcc",
        "Application": "#99ccff",
        "Technology": "#cce5ff",
        "Motivation": "#ffffff",
        "Strategy": "#ffeecc",
        "Implementation": "#e5ffcc",
        "Physical": "#cce5ff",
    }
    name = layer.value if hasattr(layer, "value") else str(layer)
    return colors.get(name, "#ffffff")


# ---------------------------------------------------------------------------
# Review Markdown
# ---------------------------------------------------------------------------


def generate_review(model: ArchiMateModel) -> str:
    """Generate review Markdown document for the architect."""
    issues = validate_model(model)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    parts: list[str] = []
    parts.append(f"# Preflight Model Review")
    parts.append("")
    parts.append(f"| Field | Value |")
    parts.append(f"|-------|-------|")
    parts.append(f"| **Proposal** | {model.name.replace('Preflight — ', '')} |")
    parts.append(f"| **PSA ID** | {model.psa_id or '—'} |")
    parts.append(f"| **Date** | {date.today().isoformat()} |")
    parts.append(f"| **Elements** | {len(model.elements)} |")
    parts.append(f"| **Relationships** | {len(model.relationships)} |")
    parts.append(f"| **Errors** | {len(errors)} |")
    parts.append(f"| **Warnings** | {len(warnings)} |")
    parts.append("")

    if errors:
        parts.append(
            "> **ERRORS FOUND** — These will prevent Archi from importing the file. Fix in corrections.yaml."
        )
        parts.append("")
        for e in errors[:10]:
            parts.append(f"- [{e.element_id}] {e.message}")
        if len(errors) > 10:
            parts.append(f"- ... and {len(errors) - 10} more")
        parts.append("")

    if warnings:
        parts.append("<details><summary>⚠️ Warnings ({count})</summary>".format(count=len(warnings)))
        parts.append("")
        for w in warnings[:20]:
            parts.append(f"- [{w.element_id}] {w.message}")
        if len(warnings) > 20:
            parts.append(f"- ... and {len(warnings) - 20} more")
        parts.append("")
        parts.append("</details>")
        parts.append("")

    parts.append("---")
    parts.append("")
    parts.append(f"## Proposed Elements ({len(model.elements)})")
    parts.append("")
    parts.append("| # | ID | Name | ArchiMate Type | Layer | Why |")
    parts.append("|---|----|------|---------------|-------|-----|")
    for idx, elem in enumerate(model.elements, 1):
        parts.append(
            f"| {idx} | `{elem.id}` | {elem.name} | "
            f"{elem.type.value} | {elem.layer.value} | {elem.why} |"
        )
    parts.append("")

    parts.append(f"## Proposed Relationships ({len(model.relationships)})")
    parts.append("")
    parts.append("| # | ID | Source | Type | Target | Why |")
    parts.append("|---|----|--------|------|--------|-----|")
    for idx, rel in enumerate(model.relationships, 1):
        src_elem = model.element_by_id(rel.source_id)
        tgt_elem = model.element_by_id(rel.target_id)
        src_name = src_elem.name if src_elem else rel.source_id
        tgt_name = tgt_elem.name if tgt_elem else rel.target_id
        arrow = _rel_arrow(rel)
        parts.append(f"| {idx} | `{rel.id}` | {src_name} | {arrow} | {tgt_name} | {rel.why} |")
    parts.append("")

    parts.append("---")
    parts.append("")
    parts.append("## Diagram Preview (Mermaid)")
    parts.append("")
    parts.append("```mermaid")
    parts.append(model_to_mermaid(model))
    parts.append("```")
    parts.append("")

    parts.append("---")
    parts.append("")
    parts.append(generate_corrections_template(model))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Corrections YAML template
# ---------------------------------------------------------------------------


def generate_corrections_template(model: ArchiMateModel) -> str:
    """Generate a corrections.yaml template with all current elements commented out."""
    parts: list[str] = []
    parts.append("## Corrections")
    parts.append("")
    parts.append(
        f"Edit `{model.psa_id or 'PSA-XXXXXXXX'}-corrections.yaml` to make changes, then run:"
    )
    parts.append("```")
    parts.append(
        f"  preflight apply-corrections {model.psa_id or 'PSA-XXXXXXXX'}-corrections.yaml --output archimate"
    )
    parts.append("```")
    parts.append("")
    parts.append("```yaml")
    parts.append("# Corrections for Preflight model — uncomment and edit as needed")
    parts.append("")

    parts.append("# elements_to_add:")
    parts.append('#   - name: ""')
    parts.append("#     type: ApplicationService  # See ElementType enum")
    parts.append("#     layer: Application")
    parts.append('#     documentation: ""')
    parts.append("")

    if model.elements:
        parts.append("# elements_to_change:")
        for elem in model.elements:
            parts.append(f"#   - id: {elem.id}")
            parts.append(f'#     # name: "{elem.name}"  # current')
            parts.append(f"#     # type: {elem.type.value}  # current — change if needed")
            parts.append("")
    else:
        parts.append("# elements_to_change: []")

    parts.append("# elements_to_remove:")
    parts.append("#   - id: id_example")
    parts.append("")

    parts.append("# relationships_to_add:")
    parts.append("#   - source: id_proposed_xxx")
    parts.append("#     type: ServingRelationship")
    parts.append("#     target: id_app_xxx")
    parts.append("")

    if model.relationships:
        parts.append("# relationships_to_change:")
        for rel in model.relationships:
            src = model.element_by_id(rel.source_id)
            tgt = model.element_by_id(rel.target_id)
            parts.append(f"#   - id: {rel.id}")
            parts.append(f"#     # source: {rel.source_id} ({src.name if src else '?'})")
            parts.append(f"#     # target: {rel.target_id} ({tgt.name if tgt else '?'})")
            parts.append(f"#     # type: {rel.type.value}  # current — change if needed")
            parts.append("")
    else:
        parts.append("# relationships_to_change: []")

    parts.append("# relationships_to_remove:")
    parts.append("#   - id: rel_example")
    parts.append("")

    parts.append("# notes:")
    parts.append('#   - ""')
    parts.append("```")

    return "\n".join(parts)


def generate_corrections_yaml(model: ArchiMateModel) -> str:
    """Generate the corrections YAML file (same template, but valid YAML)."""
    import yaml

    template: dict[str, Any] = {
        "elements_to_add": [],
        "elements_to_change": [],
        "elements_to_remove": [],
        "relationships_to_add": [],
        "relationships_to_change": [],
        "relationships_to_remove": [],
        "notes": [],
    }
    return yaml.dump(template, default_flow_style=False, allow_unicode=True, sort_keys=False)
