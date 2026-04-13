"""
Preflight guardrail configuration — which rails are active, thresholds, authority overrides.

Mirrors the config dataclass pattern from experiment/config.py.
All thresholds are configurable so the calibration loop (Phase 5) can tune them
without code changes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CitationRailConfig:
    enabled: bool = True
    min_faithfulness_score: float = 0.8
    min_verified_citations: int = 1
    authority_min_verified_citations: int = 2
    block_unverified_regulatory: bool = True
    block_hallucinated_sources: bool = True


@dataclass
class AuthorityRailConfig:
    enabled: bool = True
    authority_persona_ids: tuple[str, ...] = (
        "security",
        "risk",
        "fg-dpo",
        "cmio",
    )
    veto_persona_ids: tuple[str, ...] = ("security",)
    escalation_persona_ids: tuple[str, ...] = ("risk",)
    independent_persona_ids: tuple[str, ...] = ("fg-dpo",)
    patient_safety_persona_ids: tuple[str, ...] = ("cmio",)
    require_human_signoff: bool = True
    block_override_without_signoff: bool = True


@dataclass
class ClinicalSystemRailConfig:
    enabled: bool = True
    clinical_request_types: tuple[str, ...] = ("clinical-system",)
    clinical_impact_floor: str = "high"
    block_fast_track: bool = True
    require_cmio_perspective: bool = True


@dataclass
class PatientDataRailConfig:
    enabled: bool = True
    patient_data_request_types: tuple[str, ...] = ("patient-data", "clinical-system")
    patient_data_keywords: tuple[str, ...] = (
        "patient data",
        "persoonsgegevens",
        "zorggegevens",
        "patiëntdata",
        "avg",
        "gdpr",
        "dpia",
        "bsn",
        "burger service nummer",
        "medische data",
        "health data",
    )
    require_dpia: bool = True
    require_fg_dpo: bool = True
    dpia_template: str = "dpia"


@dataclass
class OutputValidationRailConfig:
    enabled: bool = True
    required_products: tuple[str, ...] = ("psa",)
    template_dir: str = ""
    block_unresolved_placeholders: bool = True
    max_unresolved_placeholders: int = 5
    block_missing_sections: bool = True


@dataclass
class GuardrailConfig:
    citation: CitationRailConfig = field(default_factory=CitationRailConfig)
    authority: AuthorityRailConfig = field(default_factory=AuthorityRailConfig)
    clinical_system: ClinicalSystemRailConfig = field(default_factory=ClinicalSystemRailConfig)
    patient_data: PatientDataRailConfig = field(default_factory=PatientDataRailConfig)
    output_validation: OutputValidationRailConfig = field(
        default_factory=OutputValidationRailConfig
    )

    nemo_guardrails_enabled: bool = False
    shadow_mode: bool = True
    abort_on_block: bool = False

    @property
    def active_rail_names(self) -> list[str]:
        names: list[str] = []
        if self.citation.enabled:
            names.append("citation")
        if self.authority.enabled:
            names.append("authority")
        if self.clinical_system.enabled:
            names.append("clinical_system")
        if self.patient_data.enabled:
            names.append("patient_data")
        if self.output_validation.enabled:
            names.append("output_validation")
        return names


DEFAULT_CONFIG = GuardrailConfig()

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent.parent / "config" / "guardrails.json"


def load_guardrail_config(path: str | None = None) -> GuardrailConfig:
    config_path = Path(path) if path else CONFIG_FILE
    if not config_path.exists():
        return GuardrailConfig()
    with open(config_path) as f:
        data = json.load(f)
    return GuardrailConfig(
        citation=CitationRailConfig(**data.get("citation", {})),
        authority=AuthorityRailConfig(**data.get("authority", {})),
        clinical_system=ClinicalSystemRailConfig(**data.get("clinical_system", {})),
        patient_data=PatientDataRailConfig(**data.get("patient_data", {})),
        output_validation=OutputValidationRailConfig(**data.get("output_validation", {})),
        nemo_guardrails_enabled=data.get("nemo_guardrails_enabled", False),
        shadow_mode=data.get("shadow_mode", True),
        abort_on_block=data.get("abort_on_block", False),
    )


def save_guardrail_config(config: GuardrailConfig, path: str | None = None) -> None:
    config_path = Path(path) if path else CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)
