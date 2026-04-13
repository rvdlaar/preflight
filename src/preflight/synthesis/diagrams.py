"""
ArchiMate diagram generation — draw.io XML + Mermaid output.

Generates structured diagram data from assessment context.
Diagrams are DRAFTS — human rearranges in draw.io.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# ArchiMate element types -> draw.io shapes
# ---------------------------------------------------------------------------

ARCHIMATE_SHAPES: dict[str, dict[str, str]] = {
    "BusinessActor": {
        "shape": "mxgraph.archimate.business.actor",
        "fill": "#FFFFCC",
        "stroke": "#000000",
    },
    "BusinessRole": {
        "shape": "mxgraph.archimate.business.role",
        "fill": "#FFFFCC",
        "stroke": "#000000",
    },
    "BusinessFunction": {
        "shape": "mxgraph.archimate.business.function",
        "fill": "#FFFFCC",
        "stroke": "#000000",
    },
    "BusinessProcess": {
        "shape": "mxgraph.archimate.business.process",
        "fill": "#FFFFCC",
        "stroke": "#000000",
    },
    "BusinessService": {
        "shape": "mxgraph.archimate.business.service",
        "fill": "#FFFFCC",
        "stroke": "#000000",
    },
    "ApplicationComponent": {
        "shape": "mxgraph.archimate.application.component",
        "fill": "#99CCFF",
        "stroke": "#000000",
    },
    "ApplicationFunction": {
        "shape": "mxgraph.archimate.application.function",
        "fill": "#99CCFF",
        "stroke": "#000000",
    },
    "ApplicationService": {
        "shape": "mxgraph.archimate.application.service",
        "fill": "#99CCFF",
        "stroke": "#000000",
    },
    "DataObject": {
        "shape": "mxgraph.archimate.application.dataobject",
        "fill": "#99CCFF",
        "stroke": "#000000",
    },
    "Node": {
        "shape": "mxgraph.archimate.technology.node",
        "fill": "#CCE5FF",
        "stroke": "#000000",
    },
    "SystemSoftware": {
        "shape": "mxgraph.archimate.technology.systemsoftware",
        "fill": "#CCE5FF",
        "stroke": "#000000",
    },
    "TechnologyService": {
        "shape": "mxgraph.archimate.technology.service",
        "fill": "#CCE5FF",
        "stroke": "#000000",
    },
    "Stakeholder": {
        "shape": "mxgraph.archimate.motivation.stakeholder",
        "fill": "#FFFFFF",
        "stroke": "#000000",
    },
    "Requirement": {
        "shape": "mxgraph.archimate.motivation.requirement",
        "fill": "#FFFFFF",
        "stroke": "#000000",
    },
    "Principle": {
        "shape": "mxgraph.archimate.motivation.principle",
        "fill": "#FFFFFF",
        "stroke": "#000000",
    },
}

DEFAULT_SHAPE: dict[str, str] = {
    "shape": "rectangle",
    "fill": "#FFFFFF",
    "stroke": "#000000",
}

RELATIONSHIP_STYLES: dict[str, dict[str, str]] = {
    "Serving": {"style": "dashed=0;endArrow=open;endFill=0;", "label": "serves"},
    "Access": {"style": "dashed=0;endArrow=open;endFill=0;", "label": "accesses"},
    "Flow": {"style": "dashed=0;endArrow=open;endFill=0;", "label": "flow"},
    "Triggering": {"style": "dashed=0;endArrow=open;endFill=1;", "label": "triggers"},
    "Realization": {"style": "dashed=1;endArrow=open;endFill=0;", "label": "realizes"},
    "Assignment": {
        "style": "dashed=0;endArrow=open;endFill=1;",
        "label": "assigned to",
    },
    "Aggregation": {"style": "dashed=0;endArrow=diamond;endFill=0;", "label": ""},
    "Composition": {"style": "dashed=0;endArrow=diamond;endFill=1;", "label": ""},
    "Association": {"style": "dashed=0;endArrow=open;endFill=0;", "label": ""},
    "Dependency": {"style": "dashed=1;endArrow=open;endFill=0;", "label": "depends on"},
}

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

LAYER_CONFIG: dict[str, dict] = {
    "Business": {"y": 50, "color": "#FFFFCC"},
    "Application": {"y": 300, "color": "#99CCFF"},
    "Technology": {"y": 550, "color": "#CCE5FF"},
}

CELL_WIDTH = 160
CELL_HEIGHT = 60
CELL_GAP_X = 40
CELL_GAP_Y = 30


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DiagramElement:
    id: str
    name: str
    type: str
    layer: str = "Application"
    metadata: dict = field(default_factory=dict)


@dataclass
class DiagramRelationship:
    id: str
    source: str
    target: str
    type: str
    label: str = ""


@dataclass
class Diagram:
    name: str
    elements: list[DiagramElement] = field(default_factory=list)
    relationships: list[DiagramRelationship] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Layout engine
# ---------------------------------------------------------------------------


class DiagramLayout:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {
            "Business": 0,
            "Application": 0,
            "Technology": 0,
            "Other": 0,
        }

    def position(self, layer: str) -> dict[str, int]:
        cfg = LAYER_CONFIG.get(layer, {"y": 800, "color": "#FFFFFF"})
        idx = self._counters.get(layer, 0)
        self._counters[layer] = idx + 1
        return {
            "x": 50 + idx * (CELL_WIDTH + CELL_GAP_X),
            "y": cfg["y"],
        }


# ---------------------------------------------------------------------------
# Diagram generators
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    return re.sub(r"^_|_$", "", re.sub(r"[^a-z0-9]+", "_", str(name).lower()))


def generate_application_landscape(data: dict) -> Diagram:
    existing_apps = data.get("existingApps", [])
    proposed_app = data.get("proposedApp")
    integrations = data.get("integrations", [])
    data_objects = data.get("dataObjects", [])

    elements: list[DiagramElement] = []
    relationships: list[DiagramRelationship] = []

    if proposed_app:
        elements.append(
            DiagramElement(
                id="proposed",
                name=proposed_app.get("name", "[Voorgesteld systeem]"),
                type="ApplicationComponent",
                layer="Application",
                metadata={"proposed": True},
            )
        )

    for app in existing_apps:
        elem_id = f"app_{_slug(app['name'])}"
        elements.append(
            DiagramElement(
                id=elem_id,
                name=app["name"],
                type="ApplicationComponent",
                layer="Application",
                metadata={"status": app.get("status"), "overlap": app.get("overlap")},
            )
        )
        if proposed_app and app.get("relation"):
            relationships.append(
                DiagramRelationship(
                    id=f"rel_{_slug(app['name'])}_proposed",
                    source=elem_id if app["relation"] == "replaces" else "proposed",
                    target="proposed" if app["relation"] == "replaces" else elem_id,
                    type="Flow" if app["relation"] == "replaces" else "Serving",
                    label=app["relation"],
                )
            )

    for d in data_objects:
        elements.append(
            DiagramElement(
                id=f"data_{_slug(d['name'])}",
                name=d["name"],
                type="DataObject",
                layer="Application",
                metadata={"classification": d.get("classification")},
            )
        )

    for intf in integrations:
        relationships.append(
            DiagramRelationship(
                id=f"intf_{_slug(intf.get('source', 'proposed'))}_{_slug(intf.get('target', 'proposed'))}",
                source=f"app_{_slug(intf['source'])}" if intf.get("source") else "proposed",
                target=f"app_{_slug(intf['target'])}" if intf.get("target") else "proposed",
                type="Flow",
                label=intf.get("protocol", ""),
            )
        )

    return Diagram(
        name="Applicatielandschap / Application Landscape",
        elements=elements,
        relationships=relationships,
    )


def generate_integration_overview(data: dict) -> Diagram:
    integrations = data.get("integrations", [])
    proposed_app = data.get("proposedApp")

    elements: list[DiagramElement] = []
    relationships: list[DiagramRelationship] = []
    seen: set[str] = set()

    def add_app(name: str) -> str:
        aid = f"app_{_slug(name)}"
        if aid not in seen:
            seen.add(aid)
            elements.append(
                DiagramElement(id=aid, name=name, type="ApplicationComponent", layer="Application")
            )
        return aid

    elements.append(
        DiagramElement(
            id="cloverleaf",
            name="Cloverleaf",
            type="ApplicationService",
            layer="Technology",
        )
    )

    if proposed_app:
        add_app(proposed_app.get("name", "[Nieuw systeem]"))

    for intf in integrations:
        source_id = add_app(
            intf.get(
                "source",
                proposed_app.get("name", "[Bron]") if proposed_app else "[Bron]",
            )
        )
        target_id = add_app(intf.get("target", "[Doel]"))

        relationships.append(
            DiagramRelationship(
                id=f"flow_{source_id}_clv",
                source=source_id,
                target="cloverleaf",
                type="Flow",
                label=intf.get("protocolIn", intf.get("protocol", "")),
            )
        )
        relationships.append(
            DiagramRelationship(
                id=f"flow_clv_{target_id}",
                source="cloverleaf",
                target=target_id,
                type="Flow",
                label=intf.get("protocolOut", ""),
            )
        )

    return Diagram(
        name="Integratieoverzicht / Integration Overview",
        elements=elements,
        relationships=relationships,
    )


def generate_biv_diagram(data: dict) -> Diagram:
    proposed_app = data.get("proposedApp", {})
    biv = data.get("biv", {})

    elements: list[DiagramElement] = []
    relationships: list[DiagramRelationship] = []

    elements.append(
        DiagramElement(
            id="proposed",
            name=proposed_app.get("name", "[Systeem]"),
            type="ApplicationComponent",
            layer="Application",
            metadata={"biv": f"B={biv.get('B', '?')} I={biv.get('I', '?')} V={biv.get('V', '?')}"},
        )
    )

    if biv.get("B", 0) >= 3:
        elements.append(
            DiagramElement(
                id="ctrl_dr",
                name="DR Plan\n(RPO ≤1h, RTO ≤4h)",
                type="Requirement",
                layer="Other",
            )
        )
        relationships.append(
            DiagramRelationship(
                id="rel_dr", source="proposed", target="ctrl_dr", type="Realization"
            )
        )

    if biv.get("I", 0) >= 3:
        elements.append(
            DiagramElement(
                id="ctrl_val",
                name="Data validatie\nverplicht",
                type="Requirement",
                layer="Other",
            )
        )
        relationships.append(
            DiagramRelationship(
                id="rel_val", source="proposed", target="ctrl_val", type="Realization"
            )
        )

    if biv.get("V", 0) >= 3:
        elements.append(
            DiagramElement(
                id="ctrl_nen",
                name="NEN 7510 volledig\nDPIA + NEN 7513",
                type="Requirement",
                layer="Other",
            )
        )
        relationships.append(
            DiagramRelationship(
                id="rel_nen", source="proposed", target="ctrl_nen", type="Realization"
            )
        )

    return Diagram(
        name="BIV-classificatie / BIV Classification",
        elements=elements,
        relationships=relationships,
    )


def generate_zira_diagram(data: dict) -> Diagram:
    zira = data.get("zira", {})
    proposed_app = data.get("proposedApp")

    elements: list[DiagramElement] = []
    relationships: list[DiagramRelationship] = []

    if zira.get("domain"):
        elements.append(
            DiagramElement(
                id="zira_domain",
                name=zira["domain"],
                type="BusinessFunction",
                layer="Business",
            )
        )

    for bf in zira.get("businessFunctions", []):
        bf_id = f"bf_{_slug(bf['name'])}"
        elements.append(
            DiagramElement(id=bf_id, name=bf["name"], type="BusinessFunction", layer="Business")
        )
        if zira.get("domain"):
            relationships.append(
                DiagramRelationship(
                    id=f"rel_{bf_id}",
                    source=bf_id,
                    target="zira_domain",
                    type="Composition",
                )
            )

    if proposed_app:
        elements.append(
            DiagramElement(
                id="proposed",
                name=proposed_app.get("name", "[Voorgesteld systeem]"),
                type="ApplicationComponent",
                layer="Application",
            )
        )
        for bf in zira.get("businessFunctions", []):
            relationships.append(
                DiagramRelationship(
                    id=f"rel_proposed_bf_{_slug(bf['name'])}",
                    source="proposed",
                    target=f"bf_{_slug(bf['name'])}",
                    type="Serving",
                )
            )

    for idom in zira.get("informationDomains", []):
        elements.append(
            DiagramElement(
                id=f"info_{_slug(idom['name'])}",
                name=idom["name"],
                type="DataObject",
                layer="Application",
            )
        )

    return Diagram(
        name="ZiRA-positionering / ZiRA Positioning",
        elements=elements,
        relationships=relationships,
    )


# ---------------------------------------------------------------------------
# draw.io XML generation
# ---------------------------------------------------------------------------


def _escape_xml(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def diagram_to_drawio_xml(diagram: Diagram) -> str:
    """Generate mxGraphModel XML for draw.io MCP create_diagram tool.

    Uses draw.io's ArchiMate stencil library for proper shapes.
    Minimal positioning — draw.io's auto-layout handles refinement.
    Parent-child containment for swimlane layers.
    All layout is deterministic code — the LLM never generates XML.
    """
    counter = [0]
    elem_cells: dict[str, str] = {}

    def next_id() -> str:
        counter[0] += 1
        return str(counter[0])

    parts: list[str] = []

    parts.append(
        '<mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        'pageWidth="1600" pageHeight="1200" math="0" shadow="0" adaptiveColors="auto">'
    )
    parts.append("<root>")
    parts.append('<mxCell id="0"/>')
    parts.append('<mxCell id="1" parent="0"/>')

    layer_cells: dict[str, str] = {}
    for layer_name, cfg in LAYER_CONFIG.items():
        layer_id = next_id()
        layer_cells[layer_name] = layer_id
        parts.append(
            f'<mxCell id="{layer_id}" value="{_escape_xml(layer_name)}" '
            f'style="swimlane;startSize=30;fillColor={cfg["color"]};strokeColor=#666666;'
            f'fontStyle=1;fontSize=14;html=1;collapsible=0;" '
            f'vertex="1" parent="1">'
        )
        parts.append(
            f'<mxGeometry x="10" y="{cfg["y"] - 30}" width="1500" height="220" as="geometry"/>'
        )
        parts.append("</mxCell>")

    other_id = next_id()
    layer_cells["Other"] = other_id
    parts.append(
        f'<mxCell id="{other_id}" value="Motivation / Requirements" '
        f'style="swimlane;startSize=30;fillColor=#FFFFFF;strokeColor=#666666;'
        f'fontStyle=1;fontSize=14;html=1;collapsible=0;" '
        f'vertex="1" parent="1">'
    )
    parts.append(f'<mxGeometry x="10" y="800" width="1500" height="200" as="geometry"/>')
    parts.append("</mxCell>")

    layout = DiagramLayout()
    for elem in diagram.elements:
        cell_id = next_id()
        elem_cells[elem.id] = cell_id
        pos = layout.position(elem.layer or "Application")
        shape_cfg = ARCHIMATE_SHAPES.get(elem.type, DEFAULT_SHAPE)
        style = (
            f"shape={shape_cfg['shape']};fillColor={shape_cfg['fill']};"
            f"strokeColor={shape_cfg['stroke']};fontStyle=1;fontSize=12;html=1;whiteSpace=wrap;"
        )
        biv_meta = elem.metadata.get("biv", "")
        label = _escape_xml(elem.name)
        if biv_meta:
            label += f"&lt;br/&gt;&lt;i&gt;{biv_meta}&lt;/i&gt;"
        parent_id = layer_cells.get(elem.layer or "Application", "1")
        parts.append(
            f'<mxCell id="{cell_id}" value="{label}" style="{style}" vertex="1" parent="{parent_id}">'
        )
        parts.append(
            f'<mxGeometry x="{pos["x"]}" y="{pos["y"]}" width="{CELL_WIDTH}" height="{CELL_HEIGHT}" as="geometry"/>'
        )
        parts.append("</mxCell>")

    for rel in diagram.relationships:
        src = elem_cells.get(rel.source)
        tgt = elem_cells.get(rel.target)
        if not src or not tgt:
            continue
        rel_cfg = RELATIONSHIP_STYLES.get(rel.type, RELATIONSHIP_STYLES["Association"])
        cell_id = next_id()
        parts.append(
            f'<mxCell id="{cell_id}" value="{_escape_xml(rel.label)}" '
            f'style="{rel_cfg["style"]}html=1;" edge="1" source="{src}" target="{tgt}" parent="1">'
        )
        parts.append('<mxGeometry relative="1" as="geometry"/>')
        parts.append("</mxCell>")

    parts.append("</root></mxGraphModel>")
    return "".join(parts)


def diagram_to_drawio_file(diagram: Diagram) -> str:
    """Generate full .drawio file format (mxfile wrapper for saving to disk)."""
    model_xml = diagram_to_drawio_xml(diagram)
    import base64
    import zlib

    compressed = zlib.compress(model_xml.encode("utf-8"), 9)
    encoded = base64.b64encode(compressed).decode("utf-8")
    return f'<mxfile><diagram name="{_escape_xml(diagram.name)}">{encoded}</diagram></mxfile>'


def _mermaid_id(id_str: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", id_str)


def diagram_to_mermaid(diagram: Diagram) -> str:
    lines = ["graph TD"]
    for elem in diagram.elements:
        safe = _mermaid_id(elem.id)
        lines.append(f'    {safe}["{elem.name}"]')
    for rel in diagram.relationships:
        source = _mermaid_id(rel.source)
        target = _mermaid_id(rel.target)
        label = f"|{rel.label}|" if rel.label else ""
        arrow = "-.->" if rel.type in ("Realization", "Dependency") else "-->"
        lines.append(f"    {source} {arrow} {label} {target}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Master generator
# ---------------------------------------------------------------------------


def generate_diagrams(assessment_data: dict) -> dict[str, dict]:
    request_type = assessment_data.get("requestType")
    diagrams: dict[str, dict] = {}

    landscape = generate_application_landscape(assessment_data)
    diagrams["application-landscape"] = {
        "mcp_xml": diagram_to_drawio_xml(landscape),
        "drawio_file": diagram_to_drawio_file(landscape),
        "mermaid": diagram_to_mermaid(landscape),
    }

    if assessment_data.get("integrations") or request_type == "integration":
        integ = generate_integration_overview(assessment_data)
        diagrams["integration-overview"] = {
            "mcp_xml": diagram_to_drawio_xml(integ),
            "drawio_file": diagram_to_drawio_file(integ),
            "mermaid": diagram_to_mermaid(integ),
        }

    if assessment_data.get("biv"):
        biv = generate_biv_diagram(assessment_data)
        diagrams["biv-classification"] = {
            "mcp_xml": diagram_to_drawio_xml(biv),
            "drawio_file": diagram_to_drawio_file(biv),
            "mermaid": diagram_to_mermaid(biv),
        }

    if assessment_data.get("zira"):
        zira = generate_zira_diagram(assessment_data)
        diagrams["zira-positioning"] = {
            "mcp_xml": diagram_to_drawio_xml(zira),
            "drawio_file": diagram_to_drawio_file(zira),
            "mermaid": diagram_to_mermaid(zira),
        }

    return diagrams
