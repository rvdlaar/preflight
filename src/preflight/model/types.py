"""
ArchiMate 3.2 model types — elements, relationships, layers, validation.

Internal representation between PipelineResult and all output formats
(exchange XML, draw.io, Mermaid, review Markdown).

Thinking applied:
  First principles: An element has a type, name, layer. A relationship connects
  two elements with a type. The exchange XML needs identifiers, names in lang,
  properties, and documentation. That's it. Don't over-abstract.
  Second order: If the type system is too strict, the builder becomes fragile.
  If too loose, invalid models slip through and Archi rejects the import.
  Solution: strict enums for types, but validation warns rather than blocks.
  Inversion: What makes this fail? Over-engineering. The architect reviews
  anyway — validation should surface issues, not prevent model creation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------


class Layer(str, Enum):
    STRATEGY = "Strategy"
    BUSINESS = "Business"
    APPLICATION = "Application"
    TECHNOLOGY = "Technology"
    PHYSICAL = "Physical"
    MOTIVATION = "Motivation"
    IMPLEMENTATION_MIGRATION = "Implementation"


# ---------------------------------------------------------------------------
# Element types — ArchiMate 3.2 xsi:type values
# ---------------------------------------------------------------------------


class ElementType(str, Enum):
    # Strategy
    RESOURCE = "Resource"
    CAPABILITY = "Capability"
    COURSE_OF_ACTION = "CourseOfAction"
    # Business
    BUSINESS_ACTOR = "BusinessActor"
    BUSINESS_ROLE = "BusinessRole"
    BUSINESS_COLLABORATION = "BusinessCollaboration"
    BUSINESS_INTERFACE = "BusinessInterface"
    BUSINESS_FUNCTION = "BusinessFunction"
    BUSINESS_PROCESS = "BusinessProcess"
    BUSINESS_EVENT = "BusinessEvent"
    BUSINESS_SERVICE = "BusinessService"
    BUSINESS_OBJECT = "BusinessObject"
    CONTRACT = "Contract"
    REPRESENTATION = "Representation"
    PRODUCT = "Product"
    # Application
    APPLICATION_COMPONENT = "ApplicationComponent"
    APPLICATION_COLLABORATION = "ApplicationCollaboration"
    APPLICATION_INTERFACE = "ApplicationInterface"
    APPLICATION_FUNCTION = "ApplicationFunction"
    APPLICATION_PROCESS = "ApplicationProcess"
    APPLICATION_EVENT = "ApplicationEvent"
    APPLICATION_SERVICE = "ApplicationService"
    DATA_OBJECT = "DataObject"
    # Technology
    NODE = "Node"
    EQUIPMENT = "Equipment"
    FACILITY = "Facility"
    DISTRIBUTION_NETWORK = "DistributionNetwork"
    TECHNOLOGY_COLLABORATION = "TechnologyCollaboration"
    TECHNOLOGY_INTERFACE = "TechnologyInterface"
    PATH = "Path"
    COMMUNICATION_NETWORK = "CommunicationNetwork"
    TECHNOLOGY_FUNCTION = "TechnologyFunction"
    TECHNOLOGY_PROCESS = "TechnologyProcess"
    TECHNOLOGY_EVENT = "TechnologyEvent"
    TECHNOLOGY_SERVICE = "TechnologyService"
    ARTIFACT = "Artifact"
    SYSTEM_SOFTWARE = "SystemSoftware"
    DEVICE = "Device"
    # Motivation
    STAKEHOLDER = "Stakeholder"
    DRIVER = "Driver"
    ASSESSMENT = "Assessment"
    GOAL = "Goal"
    OUTCOME = "Outcome"
    PRINCIPLE = "Principle"
    REQUIREMENT = "Requirement"
    CONSTRAINT = "Constraint"
    MEANING = "Meaning"
    VALUE = "Value"
    # Implementation & Migration
    WORK_PACKAGE = "WorkPackage"
    DELIVERABLE = "Deliverable"
    PLATEAU = "Plateau"
    GAP = "Gap"
    # Cross-layer
    GROUPING = "Grouping"
    AND_JUNCTION = "AndJunction"
    OR_JUNCTION = "OrJunction"


ELEMENT_LAYER: dict[ElementType, Layer] = {
    ElementType.RESOURCE: Layer.STRATEGY,
    ElementType.CAPABILITY: Layer.STRATEGY,
    ElementType.COURSE_OF_ACTION: Layer.STRATEGY,
    ElementType.BUSINESS_ACTOR: Layer.BUSINESS,
    ElementType.BUSINESS_ROLE: Layer.BUSINESS,
    ElementType.BUSINESS_COLLABORATION: Layer.BUSINESS,
    ElementType.BUSINESS_INTERFACE: Layer.BUSINESS,
    ElementType.BUSINESS_FUNCTION: Layer.BUSINESS,
    ElementType.BUSINESS_PROCESS: Layer.BUSINESS,
    ElementType.BUSINESS_EVENT: Layer.BUSINESS,
    ElementType.BUSINESS_SERVICE: Layer.BUSINESS,
    ElementType.BUSINESS_OBJECT: Layer.BUSINESS,
    ElementType.CONTRACT: Layer.BUSINESS,
    ElementType.REPRESENTATION: Layer.BUSINESS,
    ElementType.PRODUCT: Layer.BUSINESS,
    ElementType.APPLICATION_COMPONENT: Layer.APPLICATION,
    ElementType.APPLICATION_COLLABORATION: Layer.APPLICATION,
    ElementType.APPLICATION_INTERFACE: Layer.APPLICATION,
    ElementType.APPLICATION_FUNCTION: Layer.APPLICATION,
    ElementType.APPLICATION_PROCESS: Layer.APPLICATION,
    ElementType.APPLICATION_EVENT: Layer.APPLICATION,
    ElementType.APPLICATION_SERVICE: Layer.APPLICATION,
    ElementType.DATA_OBJECT: Layer.APPLICATION,
    ElementType.NODE: Layer.TECHNOLOGY,
    ElementType.EQUIPMENT: Layer.PHYSICAL,
    ElementType.FACILITY: Layer.PHYSICAL,
    ElementType.DISTRIBUTION_NETWORK: Layer.PHYSICAL,
    ElementType.TECHNOLOGY_COLLABORATION: Layer.TECHNOLOGY,
    ElementType.TECHNOLOGY_INTERFACE: Layer.TECHNOLOGY,
    ElementType.PATH: Layer.TECHNOLOGY,
    ElementType.COMMUNICATION_NETWORK: Layer.TECHNOLOGY,
    ElementType.TECHNOLOGY_FUNCTION: Layer.TECHNOLOGY,
    ElementType.TECHNOLOGY_PROCESS: Layer.TECHNOLOGY,
    ElementType.TECHNOLOGY_EVENT: Layer.TECHNOLOGY,
    ElementType.TECHNOLOGY_SERVICE: Layer.TECHNOLOGY,
    ElementType.ARTIFACT: Layer.TECHNOLOGY,
    ElementType.SYSTEM_SOFTWARE: Layer.TECHNOLOGY,
    ElementType.DEVICE: Layer.TECHNOLOGY,
    ElementType.STAKEHOLDER: Layer.MOTIVATION,
    ElementType.DRIVER: Layer.MOTIVATION,
    ElementType.ASSESSMENT: Layer.MOTIVATION,
    ElementType.GOAL: Layer.MOTIVATION,
    ElementType.OUTCOME: Layer.MOTIVATION,
    ElementType.PRINCIPLE: Layer.MOTIVATION,
    ElementType.REQUIREMENT: Layer.MOTIVATION,
    ElementType.CONSTRAINT: Layer.MOTIVATION,
    ElementType.MEANING: Layer.MOTIVATION,
    ElementType.VALUE: Layer.MOTIVATION,
    ElementType.WORK_PACKAGE: Layer.IMPLEMENTATION_MIGRATION,
    ElementType.DELIVERABLE: Layer.IMPLEMENTATION_MIGRATION,
    ElementType.PLATEAU: Layer.IMPLEMENTATION_MIGRATION,
    ElementType.GAP: Layer.IMPLEMENTATION_MIGRATION,
    ElementType.GROUPING: Layer.BUSINESS,
    ElementType.AND_JUNCTION: Layer.BUSINESS,
    ElementType.OR_JUNCTION: Layer.BUSINESS,
}


# ---------------------------------------------------------------------------
# Relationship types — ArchiMate 3.2 xsi:type values
# ---------------------------------------------------------------------------


class RelationshipType(str, Enum):
    COMPOSITION = "Composition"
    AGGREGATION = "Aggregation"
    ASSIGNMENT = "Assignment"
    REALIZATION = "Realization"
    SERVING = "Serving"
    ACCESS = "Access"
    INFLUENCE = "Influence"
    TRIGGERING = "Triggering"
    FLOW = "Flow"
    SPECIALIZATION = "Specialization"
    ASSOCIATION = "Association"


# XML xsi:type format: "{Type}Relationship" for the exchange format
def xsi_relationship_type(rt: RelationshipType) -> str:
    return f"{rt.value}Relationship"


# ---------------------------------------------------------------------------
# Relationship direction (for Access relationships)
# ---------------------------------------------------------------------------


class AccessDirection(str, Enum):
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read-write"


# ---------------------------------------------------------------------------
# Core model types
# ---------------------------------------------------------------------------


@dataclass
class ArchiMateElement:
    id: str
    name: str
    type: ElementType
    layer: Layer = field(default=None)
    documentation: str = ""
    properties: dict[str, str] = field(default_factory=dict)
    why: str = ""

    def __post_init__(self) -> None:
        if self.layer is None:
            self.layer = ELEMENT_LAYER.get(self.type, Layer.APPLICATION)

    @property
    def xsi_type(self) -> str:
        return self.type.value


@dataclass
class ArchiMateRelationship:
    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    name: str = ""
    documentation: str = ""
    properties: dict[str, str] = field(default_factory=dict)
    why: str = ""
    influence_modifier: str = ""
    access_direction: AccessDirection | None = None

    @property
    def xsi_type(self) -> str:
        return xsi_relationship_type(self.type)


@dataclass
class ArchiMateModel:
    name: str
    documentation: str = ""
    elements: list[ArchiMateElement] = field(default_factory=list)
    relationships: list[ArchiMateRelationship] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    psa_id: str = ""
    language: str = "nl"

    def element_by_id(self, elem_id: str) -> ArchiMateElement | None:
        return next((e for e in self.elements if e.id == elem_id), None)

    def element_by_name(self, name: str) -> ArchiMateElement | None:
        return next((e for e in self.elements if e.name == name), None)

    def add_element(self, element: ArchiMateElement) -> None:
        if not self.element_by_id(element.id):
            self.elements.append(element)

    def add_relationship(self, rel: ArchiMateRelationship) -> None:
        if not any(r.id == rel.id for r in self.relationships):
            self.relationships.append(rel)

    def remove_element(self, elem_id: str) -> list[str]:
        removed_rel_ids = [
            r.id for r in self.relationships if r.source_id == elem_id or r.target_id == elem_id
        ]
        self.relationships = [
            r for r in self.relationships if r.source_id != elem_id and r.target_id != elem_id
        ]
        self.elements = [e for e in self.elements if e.id != elem_id]
        return removed_rel_ids

    def remove_relationship(self, rel_id: str) -> None:
        self.relationships = [r for r in self.relationships if r.id != rel_id]

    def replace_element_id(self, old_id: str, new_id: str) -> None:
        for e in self.elements:
            if e.id == old_id:
                e.id = new_id
        for r in self.relationships:
            if r.source_id == old_id:
                r.source_id = new_id
            if r.target_id == old_id:
                r.target_id = new_id


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    element_id: str
    message: str


def validate_model(model: ArchiMateModel) -> list[ValidationIssue]:
    """
    Validate model integrity. Returns issues (errors + warnings).

    Inversion: what makes Archi reject the import? Invalid identifiers,
    dangling relationship references, unknown xsi:types. We catch these.
    What we don't block: relationship type compatibility — the architect
    may intentionally use unusual combinations. We warn, not block.
    """
    issues: list[ValidationIssue] = []
    elem_ids = {e.id for e in model.elements}
    id_pattern = re.compile(r"^[a-zA-Z_][\w.-]*$")

    for e in model.elements:
        if not id_pattern.match(e.id):
            issues.append(
                ValidationIssue(
                    "error",
                    e.id,
                    f"Invalid identifier '{e.id}' — xs:ID must match [a-zA-Z_][\\w.-]*",
                )
            )
        if not e.name.strip():
            issues.append(
                ValidationIssue(
                    "error", e.id, "Element name is empty — exchange format requires non-empty name"
                )
            )
        try:
            ElementType(e.type.value)
        except ValueError:
            issues.append(ValidationIssue("error", e.id, f"Unknown element type '{e.type}'"))

    elem_id_counts: dict[str, int] = {}
    for e in model.elements:
        elem_id_counts[e.id] = elem_id_counts.get(e.id, 0) + 1
    for eid, count in elem_id_counts.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    "error", eid, f"Duplicate element identifier '{eid}' (count={count})"
                )
            )

    rel_id_counts: dict[str, int] = {}
    for r in model.relationships:
        rel_id_counts[r.id] = rel_id_counts.get(r.id, 0) + 1
        if not id_pattern.match(r.id):
            issues.append(
                ValidationIssue("error", r.id, f"Invalid relationship identifier '{r.id}'")
            )
        if r.source_id not in elem_ids:
            issues.append(
                ValidationIssue("error", r.id, f"Dangling source reference '{r.source_id}'")
            )
        if r.target_id not in elem_ids:
            issues.append(
                ValidationIssue("error", r.id, f"Dangling target reference '{r.target_id}'")
            )
        try:
            RelationshipType(r.type.value)
        except ValueError:
            issues.append(ValidationIssue("error", r.id, f"Unknown relationship type '{r.type}'"))

        if r.access_direction is not None and r.type != RelationshipType.ACCESS:
            issues.append(
                ValidationIssue(
                    "warning",
                    r.id,
                    f"access_direction is only meaningful on AccessRelationship, not {r.type.value}Relationship",
                )
            )

        if r.influence_modifier and r.type != RelationshipType.INFLUENCE:
            issues.append(
                ValidationIssue(
                    "warning",
                    r.id,
                    f"influence_modifier is only meaningful on InfluenceRelationship, not {r.type.value}Relationship",
                )
            )

    for rid, count in rel_id_counts.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    "error", rid, f"Duplicate relationship identifier '{rid}' (count={count})"
                )
            )

    for r in model.relationships:
        src = model.element_by_id(r.source_id)
        tgt = model.element_by_id(r.target_id)
        if src and tgt:
            issues.extend(_check_relationship_compatibility(r, src, tgt))

    return issues


def _check_relationship_compatibility(
    rel: ArchiMateRelationship,
    source: ArchiMateElement,
    target: ArchiMateElement,
) -> list[ValidationIssue]:
    """Check relationship type compatibility per ArchiMate 3.2 spec.

    Inversion: if we're too strict, we block legitimate edge cases the
    architect wants. If too loose, invalid models reach Archi. Solution:
    warn on known violations, never block. The architect's corrections.yaml
    is the control point, not our validation.
    """
    issues: list[ValidationIssue] = []
    rt = rel.type
    src_layer = source.layer
    tgt_layer = target.layer

    if rt == RelationshipType.SERVING:
        valid_src = src_layer in (Layer.APPLICATION, Layer.TECHNOLOGY, Layer.STRATEGY)
        valid_tgt = tgt_layer in (Layer.BUSINESS, Layer.APPLICATION, Layer.STRATEGY)
        if not (valid_src and valid_tgt):
            issues.append(
                ValidationIssue(
                    "warning",
                    rel.id,
                    f"ServingRelationship: {source.type.value}({src_layer.value}) → "
                    f"{target.type.value}({tgt_layer.value}) is unusual per ArchiMate 3.2",
                )
            )

    if rt == RelationshipType.REALIZATION:
        valid_src = src_layer in (
            Layer.APPLICATION,
            Layer.TECHNOLOGY,
            Layer.STRATEGY,
            Layer.IMPLEMENTATION_MIGRATION,
        )
        valid_tgt = tgt_layer in (
            Layer.BUSINESS,
            Layer.APPLICATION,
            Layer.TECHNOLOGY,
            Layer.STRATEGY,
            Layer.MOTIVATION,
        )
        if not (valid_src and valid_tgt):
            issues.append(
                ValidationIssue(
                    "warning",
                    rel.id,
                    f"RealizationRelationship: {source.type.value}({src_layer.value}) → "
                    f"{target.type.value}({tgt_layer.value}) is unusual per ArchiMate 3.2",
                )
            )

    if rt == RelationshipType.FLOW:
        dynamic_types = {
            ElementType.BUSINESS_PROCESS,
            ElementType.BUSINESS_EVENT,
            ElementType.BUSINESS_FUNCTION,
            ElementType.BUSINESS_SERVICE,
            ElementType.APPLICATION_PROCESS,
            ElementType.APPLICATION_EVENT,
            ElementType.APPLICATION_FUNCTION,
            ElementType.APPLICATION_SERVICE,
            ElementType.TECHNOLOGY_PROCESS,
            ElementType.TECHNOLOGY_EVENT,
            ElementType.TECHNOLOGY_FUNCTION,
            ElementType.TECHNOLOGY_SERVICE,
            ElementType.AND_JUNCTION,
            ElementType.OR_JUNCTION,
        }
        if source.type not in dynamic_types and target.type not in dynamic_types:
            issues.append(
                ValidationIssue(
                    "warning",
                    rel.id,
                    f"FlowRelationship: {source.type.value} → {target.type.value} — "
                    f"typically connects dynamic/behavioral elements",
                )
            )

    if rt == RelationshipType.ASSIGNMENT:
        structural_types = {
            ElementType.BUSINESS_ACTOR,
            ElementType.BUSINESS_ROLE,
            ElementType.BUSINESS_INTERFACE,
            ElementType.BUSINESS_COLLABORATION,
            ElementType.APPLICATION_COMPONENT,
            ElementType.APPLICATION_INTERFACE,
            ElementType.APPLICATION_COLLABORATION,
            ElementType.NODE,
            ElementType.TECHNOLOGY_INTERFACE,
            ElementType.TECHNOLOGY_COLLABORATION,
        }
        if source.type not in structural_types and target.type not in structural_types:
            issues.append(
                ValidationIssue(
                    "warning",
                    rel.id,
                    f"AssignmentRelationship: {source.type.value} → {target.type.value} — "
                    f"typically assigns active structure to behavioral elements",
                )
            )

    return issues


def has_errors(model: ArchiMateModel) -> bool:
    return any(i.severity == "error" for i in validate_model(model))


# ---------------------------------------------------------------------------
# ID generation — deterministic from content, stable across runs
# ---------------------------------------------------------------------------


def make_element_id(prefix: str, name: str) -> str:
    """Generate a stable, xs:ID-valid identifier from name.

    Deterministic: same name → same ID. This means two pipeline runs
    produce the same element IDs, enabling idempotent re-import.
    """
    slug = re.sub(r"[^a-zA-Z0-9]", "_", name.strip()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return f"id_{prefix}_{slug}"


def make_relationship_id(source_id: str, rel_type: str, target_id: str) -> str:
    slug_src = source_id.replace("id_", "")
    slug_tgt = target_id.replace("id_", "")
    type_slug = rel_type.lower().replace("relationship", "")
    return f"rel_{slug_src}_{type_slug}_{slug_tgt}"
