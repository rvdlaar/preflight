"""
Preflight GuardrailEngine — runs all rails against an AssessmentContext.

Design decisions:
- Pure-Python by default, NeMo Guardrails integration if installed
- Shadow mode: log blocks but don't prevent delivery (for calibration)
- Rails run in order: Citation → Authority → ClinicalSystem → PatientData → Output
- Early exit on BLOCK (unless shadow mode)
- Results aggregate into a single GuardrailReport with overall pass/fail

Second-order thinking:
- The engine itself should be a thin orchestrator — all logic lives in rails
- Shadow mode prevents the calibration kill metric (false fast-track >10%) from
  stopping real work while we gather data
- The report must be serializable for the audit trail (NEN 7513)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from preflight.guardrails.config import GuardrailConfig
from preflight.guardrails.rails import (
    AssessmentContext,
    AuthorityRail,
    BaseRail,
    ClinicalSystemRail,
    CitationRail,
    GuardrailAction,
    GuardrailResult,
    OutputValidationRail,
    PatientDataRail,
)

logger = logging.getLogger(__name__)

RAIL_ORDER = ["citation", "authority", "clinical_system", "patient_data", "output_validation"]

RAIL_MAP: dict[str, type[BaseRail]] = {
    "citation": CitationRail,
    "authority": AuthorityRail,
    "clinical_system": ClinicalSystemRail,
    "patient_data": PatientDataRail,
    "output_validation": OutputValidationRail,
}


@dataclass
class GuardrailReport:
    overall_passed: bool
    overall_action: str
    results: list[GuardrailResult] = field(default_factory=list)
    context_summary: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    shadow_mode: bool = False
    engine_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "overall_action": self.overall_action,
            "results": [r.to_dict() for r in self.results],
            "context_summary": self.context_summary,
            "timestamp": self.timestamp,
            "shadow_mode": self.shadow_mode,
            "engine_version": self.engine_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @property
    def blocked_rails(self) -> list[str]:
        return [r.rail_name for r in self.results if r.is_block]

    @property
    def warning_rails(self) -> list[str]:
        return [r.rail_name for r in self.results if r.is_warn]

    @property
    def block_reasons(self) -> list[str]:
        return [r.reason for r in self.results if r.is_block]


class GuardrailEngine:
    """Orchestrates guardrail execution against an AssessmentContext.

    Usage:
        engine = GuardrailEngine(GuardrailConfig())
        report = engine.check(context)
        if not report.overall_passed:
            # Handle block/escalation
    """

    def __init__(self, config: GuardrailConfig | None = None):
        self.config = config or GuardrailConfig()
        self.rails: list[BaseRail] = []
        self._nemo_available = False
        self._build_rails()

    def _build_rails(self) -> None:
        active = self.config.active_rail_names
        for rail_name in RAIL_ORDER:
            if rail_name in active and rail_name in RAIL_MAP:
                rail_cls = RAIL_MAP[rail_name]
                if rail_name == "citation":
                    self.rails.append(rail_cls(self.config.citation))
                elif rail_name == "authority":
                    self.rails.append(rail_cls(self.config.authority))
                elif rail_name == "clinical_system":
                    self.rails.append(rail_cls(self.config.clinical_system))
                elif rail_name == "patient_data":
                    self.rails.append(rail_cls(self.config.patient_data))
                elif rail_name == "output_validation":
                    self.rails.append(rail_cls(self.config.output_validation))

        if self.config.nemo_guardrails_enabled:
            self._nemo_available = self._check_nemo_available()

    def _check_nemo_available(self) -> bool:
        try:
            import nemoguardrails  # noqa: F401

            return True
        except ImportError:
            logger.info("nemoguardrails not installed — using pure-Python rail enforcement")
            return False

    def check(self, context: AssessmentContext) -> GuardrailReport:
        """Run all active rails against the assessment context.

        In shadow mode, blocks are logged but the overall result is not failed.
        This allows gathering calibration data without disrupting the pipeline.
        """
        results: list[GuardrailResult] = []
        overall_passed = True
        overall_action = GuardrailAction.PASS.value

        for rail in self.rails:
            try:
                result = rail.check(context)
            except Exception as exc:
                logger.exception(f"Guardrail rail {rail.rail_name} raised an exception")
                result = GuardrailResult(
                    passed=False,
                    rail_name=rail.rail_name,
                    reason=f"Rail execution error: {exc}",
                    action=GuardrailAction.ESCALATE.value,
                    metadata={"error": str(exc)},
                )

            results.append(result)

            if not result.passed and result.is_block:
                if not self.config.shadow_mode:
                    overall_passed = False
                    if result.action == GuardrailAction.BLOCK.value:
                        overall_action = GuardrailAction.BLOCK.value
                        break
                    elif result.action == GuardrailAction.ESCALATE.value:
                        if overall_action != GuardrailAction.BLOCK.value:
                            overall_action = GuardrailAction.ESCALATE.value

                if not self.config.shadow_mode:
                    logger.warning(f"Guardrail BLOCK from {result.rail_name}: {result.reason}")
                else:
                    logger.warning(
                        f"Guardrail BLOCK (shadow mode, not enforced) from {result.rail_name}: {result.reason}"
                    )
            elif result.is_warn:
                if overall_action == GuardrailAction.PASS.value:
                    overall_action = GuardrailAction.WARN.value

        if self.config.shadow_mode and not overall_passed:
            overall_passed = True
            if overall_action == GuardrailAction.BLOCK.value:
                overall_action = GuardrailAction.WARN.value
            elif overall_action == GuardrailAction.ESCALATE.value:
                overall_action = GuardrailAction.WARN.value

        context_summary = {
            "request_type": context.request_type,
            "impact_level": context.impact_level,
            "triage_treatment": context.triage_treatment,
            "num_persona_findings": len(context.persona_findings),
            "num_retrieved_sources": len(context.retrieved_source_ids),
            "num_output_products": len(context.output_products),
            "has_fast_track": context.has_fast_track,
            "has_patient_data": context.has_patient_data,
            "has_clinical_system": context.has_clinical_system,
        }

        report = GuardrailReport(
            overall_passed=overall_passed,
            overall_action=overall_action,
            results=results,
            context_summary=context_summary,
            shadow_mode=self.config.shadow_mode,
        )

        if self._nemo_available and self.config.nemo_guardrails_enabled:
            self._run_nemo_supplementary(context, report)

        return report

    def _run_nemo_supplementary(self, context: AssessmentContext, report: GuardrailReport) -> None:
        """Run NeMo Guardrails as a supplementary check.

        NeMo runs AFTER the pure-Python rails. It cannot override a PASS to BLOCK,
        but it CAN add additional warnings. This preserves the pure-Python layer
        as the authoritative enforcement mechanism.
        """
        try:
            from preflight.guardrails.colang import run_nemo_guardrails

            nemo_result = run_nemo_guardrails(context, self.config)
            if nemo_result:
                if not nemo_result.passed:
                    report.results.append(nemo_result)
                    if nemo_result.is_block and not self.config.shadow_mode:
                        report.overall_passed = False
                        report.overall_action = GuardrailAction.WARN.value
        except Exception as exc:
            logger.warning(f"NeMo Guardrails supplementary check failed: {exc}")

    def add_rail(self, rail: BaseRail) -> None:
        """Add a custom rail to the engine."""
        self.rails.append(rail)

    def remove_rail(self, rail_name: str) -> None:
        """Remove a rail by name."""
        self.rails = [r for r in self.rails if r.rail_name != rail_name]
