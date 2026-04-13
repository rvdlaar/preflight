"""
Tests for model builder — PipelineResult → ArchiMateModel.

Thinking applied:
  Inversion: What makes the builder fail? Missing/incomplete pipeline data.
  We test with minimal, typical, and rich PipelineResult objects.
  First principles: Every element must have a 'why'. No hallucinated elements.
"""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass, field

from preflight.model.builder import build_model
from preflight.model.types import (
    ArchiMateModel,
    ElementType,
    Layer,
    RelationshipType,
    validate_model,
    has_errors,
)


@dataclass
class MockClassification:
    request_type: str = "new-application"
    impact_level: str = "medium"
    summary_en: str = "Replace LIS with Sysmex"


@dataclass
class MockPipelineResult:
    id: str = "PSA-20260412"
    classification: MockClassification = field(default_factory=MockClassification)
    biv: dict = field(
        default_factory=lambda: {"B": 3, "I": 3, "V": 3, "rpo": "≤1 uur", "rto": "≤4 uur"}
    )
    biv_controls: list = field(
        default_factory=lambda: [
            {"requirement": "DR Plan mandatory", "standard": "NEN 7510", "reference": "B=3"},
            {"requirement": "NEN 7513 audit logging", "standard": "NEN 7513", "reference": "I=3"},
        ]
    )
    conditions: list = field(
        default_factory=lambda: [
            {
                "condition_text": "Pseudonymisation required for patient data",
                "source_persona": "FG-DPO",
            },
        ]
    )
    authority_actions: list = field(
        default_factory=lambda: [
            {
                "type": "VETO",
                "persona": "security",
                "triggered": True,
                "findings": ["Security architecture concern"],
            },
        ]
    )
    persona_findings: list = field(default_factory=list)
    principetoets: dict = field(
        default_factory=lambda: {
            "principles": [
                {
                    "number": 2,
                    "name": "Veilig en vertrouwd",
                    "assessment": "Niet",
                    "definition": "Is it safe?",
                },
                {
                    "number": 4,
                    "name": "Continu",
                    "assessment": "Voldoet",
                    "definition": "Is it continuous?",
                },
            ]
        }
    )
    documents: dict = field(default_factory=dict)
    language: str = "nl"
    retrieved_context: dict = field(default_factory=dict)
    persona_contexts: list = field(default_factory=list)


class TestBuilderMinimal:
    def test_minimal_result_produces_model(self):
        result = MockPipelineResult()
        model = build_model(result)
        assert isinstance(model, ArchiMateModel)
        assert len(model.elements) > 0
        assert len(model.relationships) > 0

    def test_proposed_element_exists(self):
        result = MockPipelineResult()
        model = build_model(result)
        proposed = [e for e in model.elements if "id_proposed_" in e.id]
        assert len(proposed) == 1
        assert proposed[0].type == ElementType.APPLICATION_COMPONENT

    def test_every_element_has_why(self):
        result = MockPipelineResult()
        model = build_model(result)
        for elem in model.elements:
            assert elem.why, f"Element {elem.id} '{elem.name}' has no 'why' provenance"

    def test_every_relationship_has_why(self):
        result = MockPipelineResult()
        model = build_model(result)
        for rel in model.relationships:
            assert rel.why, f"Relationship {rel.id} has no 'why' provenance"


class TestBuilderBIV:
    def test_biv_elements_created(self):
        result = MockPipelineResult()
        model = build_model(result)
        biv_elems = [e for e in model.elements if e.id.startswith("id_biv_")]
        assert len(biv_elems) == 3  # B, I, V all >= 2

    def test_biv_controls_created(self):
        result = MockPipelineResult()
        model = build_model(result)
        ctrl_elems = [e for e in model.elements if e.id.startswith("id_ctrl_")]
        assert len(ctrl_elems) >= 2

    def test_biv_low_excludes_controls(self):
        result = MockPipelineResult(biv={"B": 1, "I": 1, "V": 1})
        model = build_model(result)
        biv_elems = [e for e in model.elements if e.id.startswith("id_biv_")]
        assert len(biv_elems) == 0


class TestBuilderConditions:
    def test_condition_elements_created(self):
        result = MockPipelineResult()
        model = build_model(result)
        cond_elems = [e for e in model.elements if e.id.startswith("id_cond_")]
        assert len(cond_elems) >= 1

    def test_condition_source_persona_in_properties(self):
        result = MockPipelineResult()
        model = build_model(result)
        cond = next(e for e in model.elements if e.id.startswith("id_cond_"))
        assert cond.properties.get("preflight:source_persona") == "FG-DPO"


class TestBuilderAuthority:
    def test_triggered_authority_creates_assessment(self):
        result = MockPipelineResult()
        model = build_model(result)
        auth_elems = [e for e in model.elements if e.id.startswith("id_auth_")]
        assert len(auth_elems) >= 1
        assert auth_elems[0].type == ElementType.ASSESSMENT

    def test_untriggered_authority_ignored(self):
        result = MockPipelineResult(
            authority_actions=[
                {"type": "VETO", "persona": "security", "triggered": False, "findings": []},
            ]
        )
        model = build_model(result)
        auth_elems = [e for e in model.elements if e.id.startswith("id_auth_")]
        assert len(auth_elems) == 0


class TestBuilderClassification:
    def test_clinical_system_type(self):
        result = MockPipelineResult(
            classification=MockClassification(request_type="clinical-system"),
        )
        model = build_model(result)
        proposed = next(e for e in model.elements if "id_proposed_" in e.id)
        assert proposed.type == ElementType.APPLICATION_COMPONENT

    def test_integration_type(self):
        result = MockPipelineResult(
            classification=MockClassification(request_type="integration"),
        )
        model = build_model(result)
        proposed = next(e for e in model.elements if "id_proposed_" in e.id)
        assert proposed.type == ElementType.APPLICATION_SERVICE


class TestBuilderValidation:
    def test_built_model_passes_validation(self):
        result = MockPipelineResult()
        model = build_model(result)
        issues = validate_model(model)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0, f"Built model has errors: {[e.message for e in errors]}"

    def test_empty_result_still_valid(self):
        result = MockPipelineResult(
            biv={},
            biv_controls=[],
            conditions=[],
            authority_actions=[],
            principetoets={},
        )
        model = build_model(result)
        assert not has_errors(model)

    def test_biv_controls_as_list(self):
        result = MockPipelineResult(
            biv_controls=[
                {"requirement": "R1", "standard": "NEN 7510", "reference": "B=3"},
                {"requirement": "R2", "standard": "NEN 7513", "reference": "I=3"},
            ],
        )
        model = build_model(result)
        ctrl_elems = [e for e in model.elements if e.id.startswith("id_ctrl_")]
        assert len(ctrl_elems) == 2

    def test_biv_controls_as_dict_converted(self):
        result = MockPipelineResult(
            biv_controls={"a": {"requirement": "R1", "standard": "NEN 7510", "reference": "B=3"}},
        )
        model = build_model(result)
        ctrl_elems = [e for e in model.elements if e.id.startswith("id_ctrl_")]
        assert len(ctrl_elems) >= 1
