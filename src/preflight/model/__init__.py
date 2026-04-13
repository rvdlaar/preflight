"""
Preflight ArchiMate model package — types, builder, review, exchange, corrections.
"""

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    Layer,
    RelationshipType,
    AccessDirection,
    ELEMENT_LAYER,
    ValidationIssue,
    validate_model,
    has_errors,
    make_element_id,
    make_relationship_id,
    xsi_relationship_type,
)
from preflight.model.builder import build_model
from preflight.model.exchange import write_exchange_xml, write_exchange_file
from preflight.model.review import generate_review, generate_corrections_yaml, model_to_mermaid
from preflight.model.corrections import apply_corrections, load_and_apply
