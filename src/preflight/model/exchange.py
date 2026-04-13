"""
ArchiMate Model Exchange XML writer — archimate3 Model Exchange Format.

Produces valid XML per The Open Group ArchiMate 3.1 Model Exchange File Format.
Importable by Archi, Sparx EA, BiZZdesign, and any ArchiMate tool.

XSD: https://www.opengroup.org/xsd/archimate/3.1/archimate3_Model.xsd

Thinking applied:
  First principles: The exchange XML is the only output that matters for
  Archi import. It must validate. Invalid XML = silent import failure.
  Second order: One bad identifier kills the whole file. No partial import.
  Validation before writing is critical. We validate in types.py, escape
  here, and produce exact namespace URIs from the XSD.
  Inversion: What makes Archi reject the import? Ampersands in names,
  spaces in identifiers, missing namespace, wrong xsi:type. We handle
  all of these. What if the XSD changes? We only use the stable 3.0/3.1
  namespace — backwards compatible.
"""

from __future__ import annotations

import re
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    Layer,
    RelationshipType,
    AccessDirection,
    xsi_relationship_type,
    validate_model,
)


ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XML_NS = "http://www.w3.org/XML/1998/namespace"

register_namespace("", ARCHIMATE_NS)
register_namespace("xsi", XSI_NS)
register_namespace("dc", DC_NS)
XSI_SCHEMA = (
    "http://www.opengroup.org/xsd/archimate "
    "http://www.opengroup.org/xsd/archimate/3.0/archimate3_Model.xsd"
)
DC_SCHEMA = (
    "http://purl.org/dc/elements/1.1/ http://dublincore.org/schemas/xmls/qdc/2008/02/11/dc.xsd"
)

NS_MAP = {
    "": ARCHIMATE_NS,
    "xsi": XSI_NS,
    "dc": DC_NS,
}


def _valid_xml_id(identifier: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"id_{cleaned}"
    return cleaned or "id_unnamed"


# ---------------------------------------------------------------------------
# Folder structure per layer
# ---------------------------------------------------------------------------

LAYER_FOLDER_ORDER: list[tuple[str, str]] = [
    ("strategy", "Strategy"),
    ("business", "Business"),
    ("application", "Application"),
    ("technology", "Technology"),
    ("physical", "Physical"),
    ("motivation", "Motivation"),
    ("implementation", "Implementation & Migration"),
]


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_exchange_xml(model: ArchiMateModel) -> str:
    """Generate archimate3 Model Exchange XML from ArchiMateModel.

    Structure:
      <model>
        <metadata>          — Dublin Core
        <name>              — model name (multilingual)
        <documentation>     — model documentation
        <properties>        — Preflight-specific properties
        <elements>          — one <element> per ArchiMateElement
        <relationships>     — one <relationship> per ArchiMateRelationship
        <organizations>     — folders per layer
      </model>

    No <views> in Phase 1 — architect creates views in Archi.
    """
    issues = validate_model(model)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        import logging

        logging.getLogger(__name__).warning(
            f"Model has {len(errors)} validation errors — Archi may reject the import. "
            f"First error: {errors[0].message}"
        )

    root = Element("model")
    root.set(
        "identifier", _valid_xml_id(f"preflight_{model.psa_id or date.today().strftime('%Y%m%d')}")
    )
    root.set(
        f"{{{XSI_NS}}}schemaLocation",
        f"{XSI_SCHEMA} {DC_SCHEMA}",
    )

    _write_metadata(root, model)
    _write_name(root, model.name, model.language)
    _write_documentation(root, model.documentation, model.language)
    _write_model_properties(root, model)
    _write_elements(root, model)
    _write_relationships(root, model)
    _write_organizations(root, model)

    return _prettify(root)


def _write_metadata(parent: Element, model: ArchiMateModel) -> None:
    metadata = SubElement(parent, "metadata")
    schema_elem = SubElement(metadata, "schema")
    schema_elem.text = "Dublin Core"
    schemaversion = SubElement(schema_elem, "schemaversion")
    schemaversion.text = "1.1"
    title = SubElement(schema_elem, f"{{{DC_NS}}}title")
    title.text = model.name
    creator = SubElement(schema_elem, f"{{{DC_NS}}}creator")
    creator.text = "Preflight"
    date_elem = SubElement(schema_elem, f"{{{DC_NS}}}date")
    date_elem.text = date.today().isoformat()
    if model.psa_id:
        ident = SubElement(schema_elem, f"{{{DC_NS}}}identifier")
        ident.text = model.psa_id


def _write_name(parent: Element, name: str, lang: str = "nl") -> None:
    name_elem = SubElement(parent, "name")
    name_elem.set(f"{{{XML_NS}}}lang", lang)
    name_elem.text = name


def _write_documentation(parent: Element, text: str, lang: str = "nl") -> None:
    if not text:
        return
    doc_elem = SubElement(parent, "documentation")
    doc_elem.set(f"{{{XML_NS}}}lang", lang)
    doc_elem.text = text


def _write_model_properties(parent: Element, model: ArchiMateModel) -> None:
    if not model.properties:
        return
    props_elem = SubElement(parent, "properties")
    for key, value in model.properties.items():
        prop = SubElement(props_elem, "property")
        prop.set("propertyDefinitionRef", _valid_xml_id(f"pd_{key}"))
        value_elem = SubElement(prop, "value")
        value_elem.text = value


def _write_elements(parent: Element, model: ArchiMateModel) -> None:
    if not model.elements:
        return
    elements_elem = SubElement(parent, "elements")
    for elem in model.elements:
        _write_element(elements_elem, elem, model.language)


def _write_element(parent: Element, elem: ArchiMateElement, lang: str) -> None:
    el = SubElement(parent, "element")
    el.set("identifier", _valid_xml_id(elem.id))
    el.set(f"{{{XSI_NS}}}type", elem.xsi_type)

    name = SubElement(el, "name")
    name.set(f"{{{XML_NS}}}lang", lang)
    name.text = elem.name

    if elem.documentation:
        _write_documentation(el, elem.documentation, lang)

    if elem.properties:
        props = SubElement(el, "properties")
        for key, value in elem.properties.items():
            prop = SubElement(props, "property")
            prop.set("propertyDefinitionRef", _valid_xml_id(f"pd_{key}"))
            val = SubElement(prop, "value")
            val.text = value


def _write_relationships(parent: Element, model: ArchiMateModel) -> None:
    if not model.relationships:
        return
    rels_elem = SubElement(parent, "relationships")
    for rel in model.relationships:
        _write_relationship(rels_elem, rel, model.language)


def _write_relationship(parent: Element, rel: ArchiMateRelationship, lang: str) -> None:
    el = SubElement(parent, "relationship")
    el.set("identifier", _valid_xml_id(rel.id))
    el.set(f"{{{XSI_NS}}}type", xsi_relationship_type(rel.type))
    el.set("source", _valid_xml_id(rel.source_id))
    el.set("target", _valid_xml_id(rel.target_id))

    if rel.name:
        name = SubElement(el, "name")
        name.set(f"{{{XML_NS}}}lang", lang)
        name.text = rel.name

    if rel.documentation:
        _write_documentation(el, rel.documentation, lang)

    if rel.access_direction:
        el.set("accessType", rel.access_direction.value)

    if rel.type == RelationshipType.INFLUENCE and rel.influence_modifier:
        el.set("modifier", rel.influence_modifier)

    if rel.properties:
        props = SubElement(el, "properties")
        for key, value in rel.properties.items():
            prop = SubElement(props, "property")
            prop.set("propertyDefinitionRef", _valid_xml_id(f"pd_{key}"))
            val = SubElement(prop, "value")
            val.text = value


def _write_organizations(parent: Element, model: ArchiMateModel) -> None:
    elements_by_layer: dict[str, list[ArchiMateElement]] = {}
    for elem in model.elements:
        layer_key = (elem.layer or Layer.APPLICATION).value.lower().split("_")[0]
        elements_by_layer.setdefault(layer_key, []).append(elem)

    org = SubElement(parent, "organizations")
    for folder_key, folder_name in LAYER_FOLDER_ORDER:
        layer_elems = elements_by_layer.get(folder_key, [])
        if not layer_elems:
            continue
        item = SubElement(org, "item")
        item.set("identifier", _valid_xml_id(f"folder_{folder_key}"))
        label = SubElement(item, "name")
        label.set(f"{{{XML_NS}}}lang", model.language)
        label.text = folder_name
        for elem in layer_elems:
            ref = SubElement(item, "item")
            ref.set("identifierRef", _valid_xml_id(elem.id))


def _prettify(root: Element) -> str:
    raw = tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + raw + "\n"


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------


def write_exchange_file(model: ArchiMateModel, path: str) -> str:
    """Write exchange XML to file. Returns the file path."""
    xml_content = write_exchange_xml(model)
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(xml_content, encoding="utf-8")
    return path
