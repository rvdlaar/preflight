"""
Preflight guardrail definitions — the five rails that enforce safety boundaries.

Each rail inspects an AssessmentContext and returns a GuardrailResult.
Rails are composable: the GuardrailEngine runs them in order and aggregates results.

First principles:
- Citations are THE evidence chain — without them, claims are hallucinations
- Authority personas have special powers that CANNOT be bypassed
- Clinical systems involve patient safety — no shortcuts
- Patient data has legal obligations (AVG/GDPR Article 35 DPIA requirement)
- Output products must be structurally valid before delivery

Second order:
- If a rail blocks, the entire assessment stops (or escalates in shadow mode)
- If citation verification passes but authority review is missing, we still block
- Shadow mode logs blocks but doesn't prevent delivery (for calibration)

Inversion (what makes this fail?):
- Citation rail too strict → false positives block valid assessments
- Authority rail allows override → VETO gets bypassed, patient data leaked
- Clinical rail not strict enough → patient safety incident
- Patient data rail skips DPIA → GDPR violation, fines up to €20M
- Output rail too lenient → malformed documents reach the board
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from preflight.citation.verify import (
    CITATION_KNOWLEDGE_RE,
    CITATION_PERSONA_RE,
    CitationReport,
    build_citation_report,
    extract_citations,
    extract_regulatory_references,
    verify_regulatory_references,
)
from preflight.guardrails.config import (
    AuthorityRailConfig,
    ClinicalSystemRailConfig,
    CitationRailConfig,
    GuardrailConfig,
    OutputValidationRailConfig,
    PatientDataRailConfig,
)


class GuardrailAction(str, Enum):
    PASS = "pass"
    BLOCK = "block"
    ESCALATE = "escalate"
    WARN = "warn"


@dataclass
class GuardrailResult:
    passed: bool
    rail_name: str
    reason: str
    action: str
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.action, GuardrailAction):
            self.action = self.action.value

    @property
    def is_block(self) -> bool:
        return self.action in (GuardrailAction.BLOCK.value, GuardrailAction.ESCALATE.value)

    @property
    def is_warn(self) -> bool:
        return self.action == GuardrailAction.WARN.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "rail_name": self.rail_name,
            "reason": self.reason,
            "action": self.action,
            "metadata": self.metadata,
        }


@dataclass
class AssessmentContext:
    request_text: str
    request_type: str = ""
    impact_level: str = "medium"
    triage_treatment: str = "standard"
    assessment_mode: str = "fast"
    persona_ids: list[str] = field(default_factory=list)
    persona_findings: list[dict[str, Any]] = field(default_factory=list)
    retrieved_source_ids: list[str] = field(default_factory=list)
    known_source_ids: set[str] = field(default_factory=set)
    known_regulatory_ids: set[str] = field(default_factory=set)
    known_persona_ids: list[str] = field(default_factory=list)
    output_products: dict[str, str] = field(default_factory=dict)
    authority_determinations: dict[str, str] = field(default_factory=dict)
    has_fast_track: bool = False
    has_patient_data: bool = False
    has_clinical_system: bool = False


class BaseRail:
    rail_name: str = "base"

    def check(self, context: AssessmentContext) -> GuardrailResult:
        raise NotImplementedError


class CitationRail(BaseRail):
    """Enforce that all [§K:source-id] citations reference actually-retrieved chunks.

    Prevents hallucinated regulatory citations — the most dangerous LLM failure mode
    in a clinical/regulatory context. Authority persona outputs require N>=2 verified
    sources per claim.
    """

    rail_name = "citation"

    def __init__(self, config: CitationRailConfig | None = None):
        self.config = config or CitationRailConfig()

    def check(self, context: AssessmentContext) -> GuardrailResult:
        if not self.config.enabled:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="Citation rail disabled",
                action=GuardrailAction.PASS.value,
            )

        all_text = self._collect_text(context)
        if not all_text.strip():
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="No assessment text to verify",
                action=GuardrailAction.PASS.value,
            )

        citations = extract_citations(all_text)
        from preflight.citation.verify import verify_citations

        verified = verify_citations(
            citations,
            known_personas=context.known_persona_ids,
            known_sources=context.known_source_ids,
            retrieved_source_ids=context.retrieved_source_ids,
        )

        knowledge_cites = [c for c in verified if c.citation_type.value == "knowledge"]
        unverified_knowledge = [c for c in knowledge_cites if not c.verified]
        hallucinated = [
            c for c in unverified_knowledge if c.source_id not in context.known_source_ids
        ]

        if self.config.block_hallucinated_sources and hallucinated:
            sources = ", ".join(c.source_id for c in hallucinated[:5])
            return GuardrailResult(
                passed=False,
                rail_name=self.rail_name,
                reason=f"Hallucinated citations — sources not in knowledge base: {sources}",
                action=GuardrailAction.BLOCK.value,
                metadata={
                    "hallucinated_sources": [c.source_id for c in hallucinated],
                    "hallucinated_raw": [c.raw for c in hallucinated],
                },
            )

        authority_ids = set(AuthorityRailConfig().authority_persona_ids)
        authority_findings = [
            f for f in context.persona_findings if f.get("perspective_id", "") in authority_ids
        ]

        for finding in authority_findings:
            finding_text = self._finding_text(finding)
            finding_cites = extract_citations(finding_text)
            finding_knowledge = [c for c in finding_cites if c.citation_type.value == "knowledge"]
            verified_finding = verify_citations(
                finding_cites,
                known_personas=context.known_persona_ids,
                known_sources=context.known_source_ids,
                retrieved_source_ids=context.retrieved_source_ids,
            )
            verified_count = sum(1 for c in verified_finding if c.verified)

            if finding_knowledge and verified_count < self.config.authority_min_verified_citations:
                pid = finding.get("perspective_id", "?")
                return GuardrailResult(
                    passed=False,
                    rail_name=self.rail_name,
                    reason=(
                        f"Authority persona '{pid}' finding has {verified_count} verified "
                        f"citations, minimum is {self.config.authority_min_verified_citations} — "
                        f"mandatory review required"
                    ),
                    action=GuardrailAction.ESCALATE.value,
                    metadata={
                        "persona_id": pid,
                        "verified_count": verified_count,
                        "min_required": self.config.authority_min_verified_citations,
                    },
                )

        reg_refs = extract_regulatory_references(all_text)
        if reg_refs:
            reg_results = verify_regulatory_references(reg_refs, context.known_regulatory_ids)
            unverified_refs = [(r, e) for r, v, e in reg_results if not v]
            if self.config.block_unverified_regulatory and unverified_refs:
                ref_list = ", ".join(r for r, _ in unverified_refs[:5])
                return GuardrailResult(
                    passed=False,
                    rail_name=self.rail_name,
                    reason=f"Unverified regulatory references: {ref_list}",
                    action=GuardrailAction.ESCALATE.value,
                    metadata={
                        "unverified_refs": unverified_refs,
                    },
                )

        total = len(verified)
        verified_count = sum(1 for c in verified if c.verified)
        faithfulness = verified_count / total if total > 0 else 1.0

        if faithfulness < self.config.min_faithfulness_score:
            return GuardrailResult(
                passed=False,
                rail_name=self.rail_name,
                reason=(
                    f"Citation faithfulness score {faithfulness:.2f} below "
                    f"threshold {self.config.min_faithfulness_score}"
                ),
                action=GuardrailAction.WARN.value,
                metadata={
                    "faithfulness_score": faithfulness,
                    "threshold": self.config.min_faithfulness_score,
                    "total_citations": total,
                    "verified_citations": verified_count,
                },
            )

        return GuardrailResult(
            passed=True,
            rail_name=self.rail_name,
            reason=f"Faithfulness {faithfulness:.2f} — {verified_count}/{total} citations verified",
            action=GuardrailAction.PASS.value,
            metadata={
                "faithfulness_score": faithfulness,
                "total_citations": total,
                "verified_citations": verified_count,
            },
        )

    def _collect_text(self, context: AssessmentContext) -> str:
        parts: list[str] = []
        for finding in context.persona_findings:
            parts.append(self._finding_text(finding))
        for product_text in context.output_products.values():
            parts.append(product_text)
        return " ".join(parts)

    def _finding_text(self, finding: dict[str, Any]) -> str:
        findings = finding.get("findings", "")
        conditions = finding.get("conditions", "")
        if isinstance(findings, list):
            findings = " ".join(str(f) for f in findings)
        if isinstance(conditions, list):
            conditions = " ".join(str(c) for c in conditions)
        return f"{findings} {conditions}"


class AuthorityRail(BaseRail):
    """Prevent bypassing mandatory authority review.

    Authority types:
    - VETO (Victor/security): can block the entire proposal
    - ESCALATION (Nadia/risk): must escalate above architect
    - INDEPENDENT (FG-DPO): cannot be overruled — GDPR DPO independence
    - PATIENT_SAFETY (CMIO): floor for clinical systems — no fast-track

    All authority outputs are DRAFTS requiring human sign-off.
    """

    rail_name = "authority"

    def __init__(self, config: AuthorityRailConfig | None = None):
        self.config = config or AuthorityRailConfig()

    def check(self, context: AssessmentContext) -> GuardrailResult:
        if not self.config.enabled:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="Authority rail disabled",
                action=GuardrailAction.PASS.value,
            )

        invoked_authority: list[str] = []
        missing_authority: list[str] = []
        missing_signoffs: list[str] = []

        veto_ids = set(self.config.veto_persona_ids)
        escalation_ids = set(self.config.escalation_persona_ids)
        independent_ids = set(self.config.independent_persona_ids)
        patient_safety_ids = set(self.config.patient_safety_persona_ids)

        all_authority_ids = veto_ids | escalation_ids | independent_ids | patient_safety_ids

        invoked_persona_ids = set(context.persona_ids)
        present_authority = all_authority_ids & invoked_persona_ids

        for aid in all_authority_ids:
            persona_name = aid
            if aid in present_authority:
                invoked_authority.append(persona_name)

                has_finding = any(f.get("perspective_id") == aid for f in context.persona_findings)
                if not has_finding:
                    missing_authority.append(f"{persona_name} (invoked but no finding)")
            else:
                if context.impact_level in ("high", "critical"):
                    if aid in veto_ids or aid in escalation_ids:
                        missing_authority.append(
                            f"{persona_name} (not invoked, required for high/critical impact)"
                        )

        if self.config.require_human_signoff:
            for aid in present_authority:
                determination = context.authority_determinations.get(aid, "")
                if not determination:
                    missing_signoffs.append(aid)

        authority_findings = [
            f for f in context.persona_findings if f.get("perspective_id", "") in all_authority_ids
        ]

        for finding in authority_findings:
            pid = finding.get("perspective_id", "")
            determination = finding.get("determination", "").lower()

            if pid in independent_ids:
                if self.config.block_override_without_signoff:
                    signoff = context.authority_determinations.get(pid, "")
                    if not signoff:
                        return GuardrailResult(
                            passed=False,
                            rail_name=self.rail_name,
                            reason=(
                                f"Independent authority '{pid}' (FG-DPO) determination "
                                f"cannot be overruled — requires explicit human sign-off"
                            ),
                            action=GuardrailAction.ESCALATE.value,
                            metadata={
                                "authority_type": "independent",
                                "persona_id": pid,
                            },
                        )

            if pid in veto_ids:
                if determination in ("block", "veto"):
                    return GuardrailResult(
                        passed=False,
                        rail_name=self.rail_name,
                        reason=(
                            f"VETO authority '{pid}' has blocked this proposal — "
                            f"escalation required"
                        ),
                        action=GuardrailAction.BLOCK.value,
                        metadata={
                            "authority_type": "veto",
                            "persona_id": pid,
                            "determination": determination,
                        },
                    )

            if pid in patient_safety_ids:
                if determination in ("block", "veto", "concern"):
                    return GuardrailResult(
                        passed=False,
                        rail_name=self.rail_name,
                        reason=(
                            f"Patient safety authority '{pid}' has raised a concern — "
                            f"cannot proceed without resolution"
                        ),
                        action=GuardrailAction.ESCALATE.value,
                        metadata={
                            "authority_type": "patient_safety",
                            "persona_id": pid,
                            "determination": determination,
                        },
                    )

        if self.config.block_override_without_signoff and missing_signoffs:
            signoff_list = ", ".join(missing_signoffs)
            return GuardrailResult(
                passed=False,
                rail_name=self.rail_name,
                reason=(
                    f"Authority personas require human sign-off before delivery: {signoff_list}"
                ),
                action=GuardrailAction.ESCALATE.value,
                metadata={"missing_signoffs": missing_signoffs},
            )

        reasons: list[str] = []
        if invoked_authority:
            reasons.append(f"Authority invoked: {', '.join(invoked_authority)}")
        if not missing_authority and not missing_signoffs:
            reasons.append("All authority reviews complete")

        return GuardrailResult(
            passed=True,
            rail_name=self.rail_name,
            reason="; ".join(reasons) if reasons else "Authority checks passed",
            action=GuardrailAction.PASS.value,
            metadata={
                "invoked_authority": invoked_authority,
                "missing_authority": missing_authority,
            },
        )


class ClinicalSystemRail(BaseRail):
    """Block fast-tracking of clinical-system requests.

    Hard triage floor: clinical-system requests CANNOT be fast-tracked,
    regardless of impact level. CMIO perspective is mandatory.
    """

    rail_name = "clinical_system"

    def __init__(self, config: ClinicalSystemRailConfig | None = None):
        self.config = config or ClinicalSystemRailConfig()

    def check(self, context: AssessmentContext) -> GuardrailResult:
        if not self.config.enabled:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="Clinical system rail disabled",
                action=GuardrailAction.PASS.value,
            )

        is_clinical = (
            context.request_type in self.config.clinical_request_types
            or context.has_clinical_system
        )

        if not is_clinical:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="Not a clinical-system request",
                action=GuardrailAction.PASS.value,
            )

        reasons: list[str] = ["Clinical-system request detected"]

        impact_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        floor_level = self.config.clinical_impact_floor
        if impact_order.get(context.impact_level, 0) < impact_order.get(floor_level, 2):
            reasons.append(
                f"Impact level '{context.impact_level}' below clinical floor "
                f"'{floor_level}' — upgrading"
            )

        if self.config.block_fast_track and context.has_fast_track:
            return GuardrailResult(
                passed=False,
                rail_name=self.rail_name,
                reason="Clinical-system request cannot be fast-tracked — hard triage floor",
                action=GuardrailAction.BLOCK.value,
                metadata={
                    "request_type": context.request_type,
                    "impact_level": context.impact_level,
                    "triage_treatment": context.triage_treatment,
                },
            )

        if self.config.require_cmio_perspective:
            cmio_present = "cmio" in context.persona_ids
            if not cmio_present:
                return GuardrailResult(
                    passed=False,
                    rail_name=self.rail_name,
                    reason=(
                        "Clinical-system request requires CMIO perspective — "
                        "CMIO not in selected personas"
                    ),
                    action=GuardrailAction.ESCALATE.value,
                    metadata={
                        "request_type": context.request_type,
                        "persona_ids": context.persona_ids,
                    },
                )

        return GuardrailResult(
            passed=True,
            rail_name=self.rail_name,
            reason="; ".join(reasons),
            action=GuardrailAction.PASS.value,
            metadata={
                "request_type": context.request_type,
                "impact_level": context.impact_level,
            },
        )


class PatientDataRail(BaseRail):
    """Require DPIA and FG-DPO review for any request involving patient data.

    AVG/GDPR Article 35 mandates a DPIA when processing patient data.
    FG-DPO has independent determination authority — cannot be overruled.
    """

    rail_name = "patient_data"

    def __init__(self, config: PatientDataRailConfig | None = None):
        self.config = config or PatientDataRailConfig()

    def check(self, context: AssessmentContext) -> GuardrailResult:
        if not self.config.enabled:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="Patient data rail disabled",
                action=GuardrailAction.PASS.value,
            )

        involves_patient_data = (
            context.has_patient_data
            or context.request_type in self.config.patient_data_request_types
            or self._detect_patient_data_keywords(context.request_text)
        )

        if not involves_patient_data:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="No patient data involvement detected",
                action=GuardrailAction.PASS.value,
            )

        reasons: list[str] = ["Patient data involvement detected"]

        if self.config.require_fg_dpo:
            fg_dpo_present = "fg-dpo" in context.persona_ids
            if not fg_dpo_present:
                return GuardrailResult(
                    passed=False,
                    rail_name=self.rail_name,
                    reason=(
                        "Patient data request requires FG-DPO (independent) "
                        "perspective — FG-DPO not in selected personas"
                    ),
                    action=GuardrailAction.BLOCK.value,
                    metadata={
                        "request_type": context.request_type,
                        "has_patient_data": True,
                    },
                )
            reasons.append("FG-DPO perspective present")

            fg_dpo_determination = context.authority_determinations.get("fg-dpo", "")
            if not fg_dpo_determination:
                return GuardrailResult(
                    passed=False,
                    rail_name=self.rail_name,
                    reason=(
                        "FG-DPO (independent authority) has not issued a determination — "
                        "cannot proceed without FG-DPO sign-off"
                    ),
                    action=GuardrailAction.ESCALATE.value,
                    metadata={"missing_signoff": "fg-dpo"},
                )

        if self.config.require_dpia:
            has_dpia = self.config.dpia_template in context.output_products
            if not has_dpia:
                return GuardrailResult(
                    passed=False,
                    rail_name=self.rail_name,
                    reason=(
                        "Patient data request requires DPIA (GDPR Article 35) — "
                        "no DPIA output product generated"
                    ),
                    action=GuardrailAction.BLOCK.value,
                    metadata={
                        "request_type": context.request_type,
                        "expected_template": self.config.dpia_template,
                        "available_products": list(context.output_products.keys()),
                    },
                )
            reasons.append("DPIA product present")

        return GuardrailResult(
            passed=True,
            rail_name=self.rail_name,
            reason="; ".join(reasons),
            action=GuardrailAction.PASS.value,
            metadata={
                "request_type": context.request_type,
                "has_patient_data": True,
                "fg_dpo_present": "fg-dpo" in context.persona_ids,
                "dpia_present": self.config.dpia_template in context.output_products,
            },
        )

    def _detect_patient_data_keywords(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in self.config.patient_data_keywords)


class OutputValidationRail(BaseRail):
    """Validate output products against their Jinja2 templates before delivery.

    Checks that:
    - Required products are present
    - Templates resolve without too many unresolved placeholders
    - Critical sections are not empty
    """

    rail_name = "output_validation"

    def __init__(self, config: OutputValidationRailConfig | None = None):
        self.config = config or OutputValidationRailConfig()

    def check(self, context: AssessmentContext) -> GuardrailResult:
        if not self.config.enabled:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason="Output validation rail disabled",
                action=GuardrailAction.PASS.value,
            )

        missing_products: list[str] = []
        for req in self.config.required_products:
            if req not in context.output_products:
                missing_products.append(req)

        if missing_products:
            return GuardrailResult(
                passed=False,
                rail_name=self.rail_name,
                reason=f"Required output products missing: {', '.join(missing_products)}",
                action=GuardrailAction.BLOCK.value,
                metadata={"missing_products": missing_products},
            )

        issues: list[str] = []
        total_unresolved = 0
        product_issues: dict[str, dict[str, Any]] = {}

        for product_name, product_text in context.output_products.items():
            unresolved = self._count_unresolved_placeholders(product_text)
            total_unresolved += unresolved

            product_metadata: dict[str, Any] = {
                "unresolved_placeholders": unresolved,
                "length": len(product_text),
            }

            if (
                self.config.block_unresolved_placeholders
                and unresolved > self.config.max_unresolved_placeholders
            ):
                issues.append(
                    f"{product_name}: {unresolved} unresolved placeholders "
                    f"(max {self.config.max_unresolved_placeholders})"
                )
                product_metadata["exceeds_threshold"] = True

            if self.config.block_missing_sections:
                missing_sections = self._find_missing_sections(product_text)
                if missing_sections:
                    issues.append(
                        f"{product_name}: missing sections: {', '.join(missing_sections[:3])}"
                    )
                    product_metadata["missing_sections"] = missing_sections

            product_issues[product_name] = product_metadata

        if (
            self.config.block_unresolved_placeholders
            and total_unresolved > self.config.max_unresolved_placeholders
        ):
            return GuardrailResult(
                passed=False,
                rail_name=self.rail_name,
                reason=f"Output products have {total_unresolved} unresolved placeholders (max {self.config.max_unresolved_placeholders})",
                action=GuardrailAction.ESCALATE.value,
                metadata={
                    "total_unresolved": total_unresolved,
                    "issues": issues,
                    "products": product_issues,
                },
            )

        if issues:
            return GuardrailResult(
                passed=True,
                rail_name=self.rail_name,
                reason=f"Output validation passed with warnings: {'; '.join(issues[:3])}",
                action=GuardrailAction.WARN.value,
                metadata={
                    "total_unresolved": total_unresolved,
                    "issues": issues,
                    "products": product_issues,
                },
            )

        return GuardrailResult(
            passed=True,
            rail_name=self.rail_name,
            reason=f"All {len(context.output_products)} output products validated",
            action=GuardrailAction.PASS.value,
            metadata={
                "total_unresolved": total_unresolved,
                "products": product_issues,
            },
        )

    def _count_unresolved_placeholders(self, text: str) -> int:
        jinja_unresolved = re.findall(r"\{\{[\w.]+\}\}", text)
        architect_needed = text.count("[ARCHITECT INPUT NEEDED]")
        return len(jinja_unresolved) + architect_needed

    def _find_missing_sections(self, text: str) -> list[str]:
        empty_sections: list[str] = []
        section_pattern = re.compile(r"^##\s+(\d+\.?\s*.+)$", re.MULTILINE)
        for match in section_pattern.finditer(text):
            section_header = match.group(1)
            start = match.end()
            next_section = section_pattern.search(text, start)
            end = next_section.start() if next_section else len(text)
            section_body = text[start:end].strip()
            if len(section_body) < 10 and "[ARCHITECT INPUT NEEDED]" not in text[start:end]:
                empty_sections.append(section_header)
        return empty_sections
