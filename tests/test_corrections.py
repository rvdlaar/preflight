"""
Tests for corrections applier — load YAML, apply, re-validate.

Thinking applied:
  Inversion: What makes corrections fail? Malformed YAML, references to
  non-existent elements, incompatible type changes. We test graceful
  handling of all of these. The architect is in control; we serve them.
"""

import pytest
import yaml
from pathlib import Path

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    RelationshipType,
    validate_model,
    has_errors,
)
from preflight.model.corrections import apply_corrections, load_and_apply


class TestAddElement:
    def test_add_element(self):
        model = ArchiMateModel(name="test")
        _, log = apply_corrections(
            model,
            {
                "elements_to_add": [{"name": "Middleware", "type": "ApplicationService"}],
            },
        )
        assert any("ADD element" in msg for msg in log)
        assert model.element_by_name("Middleware") is not None

    def test_add_element_unknown_type(self):
        model = ArchiMateModel(name="test")
        _, log = apply_corrections(
            model,
            {
                "elements_to_add": [{"name": "X", "type": "UNKNOWN_TYPE"}],
            },
        )
        assert any("SKIP" in msg for msg in log)

    def test_add_element_no_name(self):
        model = ArchiMateModel(name="test")
        _, log = apply_corrections(
            model,
            {
                "elements_to_add": [{"type": "ApplicationComponent"}],
            },
        )
        assert any("SKIP" in msg for msg in log)


class TestChangeElement:
    def test_change_type(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        _, log = apply_corrections(
            model,
            {
                "elements_to_change": [{"id": "e1", "type": "ApplicationService"}],
            },
        )
        assert any("CHANGE" in msg for msg in log)
        assert model.element_by_id("e1").type == ElementType.APPLICATION_SERVICE

    def test_change_name(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        _, log = apply_corrections(
            model,
            {
                "elements_to_change": [{"id": "e1", "name": "LIS Sysmex"}],
            },
        )
        assert model.element_by_id("e1").name == "LIS Sysmex"

    def test_change_nonexistent(self):
        model = ArchiMateModel(name="test")
        _, log = apply_corrections(
            model,
            {
                "elements_to_change": [{"id": "nonexistent", "type": "ApplicationService"}],
            },
        )
        assert any("SKIP" in msg or "not found" in msg for msg in log)


class TestRemoveElement:
    def test_remove_element(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        _, log = apply_corrections(
            model,
            {
                "elements_to_remove": [{"id": "e1"}],
            },
        )
        assert model.element_by_id("e1") is None
        assert any("REMOVE" in msg for msg in log)

    def test_remove_element_cascades_relationships(self):
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
        _, log = apply_corrections(
            model,
            {
                "elements_to_remove": [{"id": "e1"}],
            },
        )
        assert len(model.relationships) == 0


class TestAddRelationship:
    def test_add_relationship(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="e2", name="Lab", type=ElementType.BUSINESS_FUNCTION))
        _, log = apply_corrections(
            model,
            {
                "relationships_to_add": [
                    {"source": "e1", "type": "ServingRelationship", "target": "e2"}
                ],
            },
        )
        assert any("ADD relationship" in msg for msg in log)
        assert len(model.relationships) == 1

    def test_add_relationship_dangling_source(self):
        model = ArchiMateModel(name="test")
        model.add_element(ArchiMateElement(id="e2", name="Lab", type=ElementType.BUSINESS_FUNCTION))
        _, log = apply_corrections(
            model,
            {
                "relationships_to_add": [
                    {"source": "e_missing", "type": "ServingRelationship", "target": "e2"}
                ],
            },
        )
        assert any("SKIP" in msg for msg in log)


class TestRemoveRelationship:
    def test_remove_relationship(self):
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
        _, log = apply_corrections(
            model,
            {
                "relationships_to_remove": [{"id": "r1"}],
            },
        )
        assert len(model.relationships) == 0


class TestNotes:
    def test_add_note(self):
        model = ArchiMateModel(name="test", documentation="Original")
        _, log = apply_corrections(
            model,
            {
                "notes": ["LIS serves lab process, not the other way around"],
            },
        )
        assert "Architect note" in model.documentation


class TestValidationAfterCorrections:
    def test_valid_after_add(self):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        model.add_element(ArchiMateElement(id="e2", name="Lab", type=ElementType.BUSINESS_FUNCTION))
        apply_corrections(
            model,
            {
                "relationships_to_add": [
                    {"source": "e1", "type": "ServingRelationship", "target": "e2"}
                ],
            },
        )
        assert not has_errors(model)

    def test_validation_reported_in_log(self):
        model = ArchiMateModel(name="test")
        _, log = apply_corrections(
            model,
            {
                "relationships_to_add": [
                    {
                        "source": "nonexistent",
                        "type": "ServingRelationship",
                        "target": "also_missing",
                    }
                ],
            },
        )
        assert any("SKIP" in msg for msg in log)


class TestLoadAndApply:
    def test_load_from_file(self, tmp_path):
        model = ArchiMateModel(name="test")
        model.add_element(
            ArchiMateElement(id="e1", name="LIS", type=ElementType.APPLICATION_COMPONENT)
        )
        corrections = {"elements_to_change": [{"id": "e1", "name": "LIS Sysmex"}]}
        yaml_path = tmp_path / "corrections.yaml"
        yaml_path.write_text(yaml.dump(corrections))
        updated, log = load_and_apply(model, str(yaml_path))
        assert updated.element_by_id("e1").name == "LIS Sysmex"

    def test_missing_file(self):
        model = ArchiMateModel(name="test")
        with pytest.raises(FileNotFoundError):
            load_and_apply(model, "/nonexistent/corrections.yaml")
