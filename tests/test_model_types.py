"""
Tests for ArchiMate model types — validation, element/relationship creation, ID generation.

Thinking applied:
  Inversion: What makes the types fail? Invalid identifiers, empty names,
  unknown types, dangling references. These are exactly what we test.
  First principles: The types are the foundation. If they're wrong,
  everything built on them is wrong. So test the foundation thoroughly.
"""

import pytest
from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    Layer,
    RelationshipType,
    AccessDirection,
    ELEMENT_LAYER,
    make_element_id,
    make_relationship_id,
    validate_model,
    has_errors,
    xsi_relationship_type,
)


class TestElementType:
    def test_all_types_have_layer(self):
        for et in ElementType:
            assert et in ELEMENT_LAYER, f"{et} missing from ELEMENT_LAYER"

    def test_xsi_type_roundtrip(self):
        for et in ElementType:
            elem = ArchiMateElement(id="test", name="Test", type=et)
            assert elem.xsi_type == et.value

    def test_auto_layer_assignment(self):
        elem = ArchiMateElement(id="t", name="T", type=ElementType.BUSINESS_FUNCTION)
        assert elem.layer == Layer.BUSINESS
        elem2 = ArchiMateElement(id="t2", name="T2", type=ElementType.APPLICATION_COMPONENT)
        assert elem2.layer == Layer.APPLICATION
        elem3 = ArchiMateElement(id="t3", name="T3", type=ElementType.REQUIREMENT)
        assert elem3.layer == Layer.MOTIVATION
        elem4 = ArchiMateElement(id="t4", name="T4", type=ElementType.GROUPING)
        assert elem4.layer is not None
        elem5 = ArchiMateElement(id="t5", name="T5", type=ElementType.AND_JUNCTION)
        assert elem5.layer is not None


class TestRelationshipType:
    def test_xsi_relationship_type(self):
        assert xsi_relationship_type(RelationshipType.SERVING) == "ServingRelationship"
        assert xsi_relationship_type(RelationshipType.COMPOSITION) == "CompositionRelationship"
        assert xsi_relationship_type(RelationshipType.REALIZATION) == "RealizationRelationship"

    def test_all_relationships_have_xsi(self):
        for rt in RelationshipType:
            xsi = xsi_relationship_type(rt)
            assert xsi.endswith("Relationship")


class TestArchiMateModel:
    def test_add_element_no_duplicates(self):
        model = ArchiMateModel(name="test")
        e1 = ArchiMateElement(id="e1", name="A", type=ElementType.APPLICATION_COMPONENT)
        e2 = ArchiMateElement(id="e1", name="A", type=ElementType.APPLICATION_COMPONENT)
        model.add_element(e1)
        model.add_element(e2)
        assert len(model.elements) == 1

    def test_add_relationship_no_duplicates(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="s", name="S", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="t", name="T", type=ElementType.BUSINESS_FUNCTION))
        r1 = ArchiMateRelationship(
            id="r1", source_id="s", target_id="t", type=RelationshipType.SERVING
        )
        r2 = ArchiMateRelationship(
            id="r1", source_id="s", target_id="t", type=RelationshipType.SERVING
        )
        model.add_relationship(r1)
        model.add_relationship(r2)
        assert len(model.relationships) == 1

    def test_remove_element_cascades_relationships(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="a", name="A", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="b", name="B", type=ElementType.BUSINESS_FUNCTION))
        model.add_element(
            ArchiMateElement(id="c", name="C", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_relationship(
            ArchiMateRelationship(
                id="r1", source_id="a", target_id="b", type=RelationshipType.SERVING
            )
        )
        model.add_relationship(
            ArchiMateRelationship(id="r2", source_id="b", target_id="c", type=RelationshipType.FLOW)
        )
        removed = model.remove_element("b")
        assert "b" not in [e.id for e in model.elements]
        assert len(model.relationships) == 0
        assert set(removed) == {"r1", "r2"}

    def test_element_by_name(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="x", name="HIS", type=ElementType.APPLICATION_COMPONENT)
        )
        assert model.element_by_name("HIS") is not None
        assert model.element_by_name("LIS") is None


class TestIdGeneration:
    def test_stable_ids(self):
        id1 = make_element_id("app", "LIS Sysmex")
        id2 = make_element_id("app", "LIS Sysmex")
        assert id1 == id2

    def test_valid_xml_id(self):
        eid = make_element_id("proposed", "LIS/Sysmex v2.0")
        assert (
            eid.isidentifier() or eid.replace("_", "").replace(".", "").replace("-", "").isalnum()
        )

    def test_relationship_id(self):
        rid = make_relationship_id("id_app_lis", "Serving", "id_bf_lab")
        assert "lis" in rid.lower() or "app" in rid.lower()
        assert "serving" in rid.lower() or "servi" in rid.lower()


class TestValidation:
    def test_valid_model_no_errors(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="e2", name="Lab", type=ElementType.BUSINESS_FUNCTION))
        model.add_relationship(
            ArchiMateRelationship(
                id="r1", source_id="e1", target_id="e2", type=RelationshipType.SERVING
            )
        )
        issues = validate_model(model)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_dangling_source_is_error(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_relationship(
            ArchiMateRelationship(
                id="r1", source_id="e1", target_id="e_missing", type=RelationshipType.SERVING
            )
        )
        issues = validate_model(model)
        errors = [i for i in issues if i.severity == "error"]
        assert any("Dangling target" in e.message for e in errors)

    def test_empty_name_is_error(self):
        elem = ArchiMateElement(id="e1", name="", type=ElementType.APPLICATION_COMPONENT)
        elem.name = ""
        model = ArchiMateModel(name="test", elements=[elem])
        issues = validate_model(model)
        errors = [i for i in issues if i.severity == "error"]
        assert any("empty" in e.message.lower() for e in errors)

    def test_duplicate_element_id_is_error(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="dup", name="A", type=ElementType.APPLICATION_COMPONENT)
        )
        model.elements.append(
            ArchiMateElement(id="dup", name="B", type=ElementType.APPLICATION_COMPONENT)
        )
        issues = validate_model(model)
        errors = [i for i in issues if i.severity == "error"]
        assert any("Duplicate" in e.message for e in errors)

    def test_serving_wrong_layers_is_warning(self):
        model = ArchiMateModel(name="test")
        model.add_element(ArchiMateElement(id="e1", name="Req", type=ElementType.REQUIREMENT))
        model.add_element(ArchiMateElement(id="e2", name="Goal", type=ElementType.GOAL))
        model.add_relationship(
            ArchiMateRelationship(
                id="r1", source_id="e1", target_id="e2", type=RelationshipType.SERVING
            )
        )
        issues = validate_model(model)
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("Serving" in w.message for w in warnings)

    def test_has_errors(self):
        model = ArchiMateModel(name="test")
        model.add_relationship(
            ArchiMateRelationship(
                id="r1",
                source_id="missing",
                target_id="also_missing",
                type=RelationshipType.SERVING,
            )
        )
        assert has_errors(model) is True

    def test_access_direction_on_non_access_is_warning(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="A", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="e2", name="B", type=ElementType.BUSINESS_FUNCTION))
        model.add_relationship(
            ArchiMateRelationship(
                id="r1",
                source_id="e1",
                target_id="e2",
                type=RelationshipType.SERVING,
                access_direction=AccessDirection.READ,
            )
        )
        issues = validate_model(model)
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("access_direction" in w.message for w in warnings)

    def test_influence_modifier_on_non_influence_is_warning(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="A", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="e2", name="B", type=ElementType.BUSINESS_FUNCTION))
        model.add_relationship(
            ArchiMateRelationship(
                id="r1",
                source_id="e1",
                target_id="e2",
                type=RelationshipType.SERVING,
                influence_modifier="++",
            )
        )
        issues = validate_model(model)
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("influence_modifier" in w.message for w in warnings)
