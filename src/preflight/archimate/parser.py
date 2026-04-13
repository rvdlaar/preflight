"""ArchiMate .archimate XML parser.

Uses xml.etree.ElementTree for robust attribute-order-independent parsing.
Regex fallback preserved for malformed XML that ET cannot handle.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Element types by layer
# ---------------------------------------------------------------------------

ELEMENT_LAYERS: dict[str, list[str]] = {
    "Business": [
        "BusinessActor",
        "BusinessRole",
        "BusinessFunction",
        "BusinessProcess",
        "BusinessService",
        "BusinessObject",
        "BusinessInteraction",
    ],
    "Application": [
        "ApplicationComponent",
        "ApplicationFunction",
        "ApplicationInterface",
        "ApplicationService",
        "DataObject",
        "ApplicationInteraction",
    ],
    "Technology": [
        "Node",
        "Device",
        "SystemSoftware",
        "TechnologyService",
        "TechnologyInterface",
        "Artifact",
        "CommunicationPath",
        "Network",
    ],
    "Motivation": [
        "Stakeholder",
        "Driver",
        "Assessment",
        "Goal",
        "Outcome",
        "Principle",
        "Requirement",
        "Constraint",
        "Meaning",
        "Value",
    ],
    "Implementation": [
        "WorkPackage",
        "Deliverable",
        "ImplementationEvent",
        "Plateau",
        "Gap",
    ],
}

ALL_ELEMENT_TYPES: list[str] = [t for types in ELEMENT_LAYERS.values() for t in types]

RELATIONSHIP_TYPES: dict[str, dict[str, str]] = {
    "Composition": {"strength": "strong"},
    "Aggregation": {"strength": "medium"},
    "Assignment": {"strength": "strong"},
    "Realization": {"strength": "strong"},
    "Serving": {"strength": "weak"},
    "Access": {"strength": "weak"},
    "Influence": {"strength": "weak"},
    "Triggering": {"strength": "medium"},
    "Flow": {"strength": "medium"},
    "Specialization": {"strength": "strong"},
    "Association": {"strength": "weak"},
}


def _find_layer(type_name: str) -> Optional[str]:
    for layer, types in ELEMENT_LAYERS.items():
        if type_name in types:
            return layer
    return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ArchiElement:
    id: str
    type: str
    name: str
    layer: Optional[str] = None
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class ArchiRelationship:
    id: str
    type: str
    source: str
    target: str


@dataclass
class ArchiMateModel:
    elements: dict[str, ArchiElement] = field(default_factory=dict)
    relationships: list[ArchiRelationship] = field(default_factory=list)
    folders: dict[str, dict] = field(default_factory=dict)
    views: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Namespace helper — ArchiMate files declare xsi namespace
# ---------------------------------------------------------------------------

_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"


def _strip_ns(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _parse_with_elementtree(xml: str) -> ArchiMateModel:
    model = ArchiMateModel()

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return model

    XSI_TYPE = f"{{{_XSI}}}type" if _XSI in xml else "xsi:type"

    for elem in root.iter():
        tag = _strip_ns(elem.tag)
        xsi_type = elem.get(XSI_TYPE) or elem.get("xsi:type")

        if tag == "element" or (xsi_type and xsi_type in ALL_ELEMENT_TYPES):
            type_name = xsi_type or ""
            eid = elem.get("id", "")
            name = elem.get("name", "")
            layer = _find_layer(type_name)

            if layer:
                props = {}
                for prop_elem in elem.iter():
                    ptag = _strip_ns(prop_elem.tag)
                    if ptag == "property":
                        pk = prop_elem.get("key", "")
                        pv = prop_elem.get("value", "")
                        if pk:
                            props[pk] = pv
                model.elements[eid] = ArchiElement(
                    id=eid, type=type_name, name=name, layer=layer, properties=props
                )

            elif (
                type_name
                and type_name in RELATIONSHIP_TYPES
                or type_name
                in {"Association", "Flow", "Serving", "Access", "Triggering"}
            ):
                source = elem.get("source", "")
                target = elem.get("target", "")
                rid = eid if eid else ""
                rtype = type_name
                if rtype in RELATIONSHIP_TYPES or rtype in {
                    "Association",
                    "Flow",
                    "Serving",
                    "Access",
                    "Triggering",
                }:
                    model.relationships.append(
                        ArchiRelationship(
                            id=rid, type=rtype, source=source, target=target
                        )
                    )

        elif tag == "folder":
            fid = elem.get("id", "")
            fname = elem.get("name", "")
            if fid:
                model.folders[fid] = {"id": fid, "name": fname}

    return model


# Regex fallback for malformed XML
_ELEM_RE = re.compile(
    r'<element\s+xsi:type="(\w+)"\s+id="([^"]+)"\s+name="([^"]*)"[^>]*\/?>'
)
_ELEM_BLOCK_RE = re.compile(
    r'<element\s+xsi:type="(\w+)"\s+id="([^"]+)"[^>]*>([\s\S]*?)<\/element>'
)
_PROP_RE = re.compile(r'<property\s+key="([^"]+)"\s+value="([^"]*)"')
_REL_RE = re.compile(
    r'<element\s+xsi:type="(\w+)"\s+id="([^"]+)"\s+source="([^"]+)"\s+target="([^"]+)"[^>]*\/?>'
)
_FOLDER_RE = re.compile(r'<folder\s+id="([^"]+)"\s+name="([^"]*)"[^>]*\/?>')


def _parse_with_regex(xml: str) -> ArchiMateModel:
    model = ArchiMateModel()

    for match in _ELEM_RE.finditer(xml):
        type_name, eid, name = match.group(1), match.group(2), match.group(3)
        layer = _find_layer(type_name)
        if layer:
            model.elements[eid] = ArchiElement(
                id=eid, type=type_name, name=name, layer=layer
            )

    for match in _ELEM_BLOCK_RE.finditer(xml):
        type_name, eid = match.group(1), match.group(2)
        body = match.group(3)
        if eid not in model.elements:
            continue
        props = {}
        for pm in _PROP_RE.finditer(body):
            props[pm.group(1)] = pm.group(2)
        model.elements[eid].properties = props

    for match in _REL_RE.finditer(xml):
        type_name, rid, source, target = (
            match.group(1),
            match.group(2),
            match.group(3),
            match.group(4),
        )
        if type_name in RELATIONSHIP_TYPES or type_name in {
            "Association",
            "Flow",
            "Serving",
            "Access",
            "Triggering",
        }:
            model.relationships.append(
                ArchiRelationship(id=rid, type=type_name, source=source, target=target)
            )

    for match in _FOLDER_RE.finditer(xml):
        model.folders[match.group(1)] = {"id": match.group(1), "name": match.group(2)}

    return model


def parse_archimate_xml(xml: str) -> ArchiMateModel:
    model = _parse_with_elementtree(xml)
    if model.elements or model.relationships:
        return model
    return _parse_with_regex(xml)


def parse_archimate(file_path: str | Path) -> ArchiMateModel:
    xml = Path(file_path).read_text(encoding="utf-8")
    return parse_archimate_xml(xml)
