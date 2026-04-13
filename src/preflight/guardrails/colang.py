"""
Preflight Colang definitions for NeMo Guardrails integration.

NeMo Guardrails is an OPTIONAL dependency. If nemoguardrails is not installed,
the GuardrailEngine falls back to pure-Python enforcement which implements the
same rules. This module provides Colang flow definitions that can be loaded
into a NeMo Guardrails configuration for conversational or LLM-integrated usage.

Design decisions:
- Colang flows mirror the pure-Python rail logic exactly
- The `nemoguardrails` import is guarded — this module can be imported without it
- When NeMo is unavailable, run_nemo_guardrails returns None (not an error)
- Colang definitions are declarative — they can be edited without Python changes
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

COLANG_DIR = Path(__file__).parent / "colang_files"

COLANG_CONFIG_YAML = """\
models:
  - type: main
    engine: custom

rails:
  input:
    flows:
      - check clinical system request
      - check patient data request
  output:
    flows:
      - validate citations
      - validate authority review
      - validate output products

instructions:
  - type: general
    content: |
      You are the Preflight guardrail system for a Dutch hospital EA assessment tool.
      You must enforce the following hard rules:

      1. NEVER allow fast-tracking of clinical-system requests
      2. NEVER allow bypassing FG-DPO (independent) determination for patient data
      3. NEVER allow VETO overrides without explicit sign-off
      4. ALWAYS flag hallucinated regulatory citations
      5. ALWAYS mark authority persona outputs as drafts requiring human confirmation

      Reference architecture: ZiRA (Ziekenhuis Referentie Architectuur)
      Regulatory frameworks: NEN 7510/7512/7513/7516/7517, AVG/GDPR, NIS2, MDR/IVDR
"""

COLANG_FLOWS = """
define flow check clinical system request
  user request involves clinical system
  !request has cmio perspective
  bot block "Clinical-system request requires CMIO perspective — cannot fast-track"
  stop

define flow check patient data request
  user request involves patient data
  !request has fg-dpo perspective
  bot block "Patient data request requires FG-DPO review — cannot proceed without DPO"
  stop

define flow validate citations
  bot output has hallucinated citations
  bot block "Citations reference sources not in knowledge base — remove or verify"
  stop

define flow validate authority review
  bot output from authority persona
  !human has signed off
  bot escalate "Authority persona output requires human sign-off"
  stop

define flow validate output products
  !output has required product "psa"
  bot block "Required output product PSA is missing"
  stop
"""

COLANG_DEFINITIONS = """
define subflow check clinical system
  user mentions clinical system
  or user mentions his or lis or epd or pacs
  or user mentions patient care or patientenzorg
  set request_type = "clinical-system"

define subflow check patient data
  user mentions patient data or persoonsgegevens
  or user mentions zorggegevens or patiëntdata
  or user mentions avg or gdpr or dpia
  set has_patient_data = true

define subflow check authority
  mention of veto or blokkade
  set authority_type = "veto"
  mention of escalatie or escalation
  set authority_type = "escalation"
  mention of fg-dpo or functionaris
  set authority_type = "independent"
"""


def run_nemo_guardrails(
    context: Any,
    config: Any,
) -> Any:
    """Run NeMo Guardrails as a supplementary check.

    Returns a GuardrailResult if NeMo is available and configured,
    None otherwise. This is called by the GuardrailEngine after
    the pure-Python rails have run.
    """
    try:
        from nemoguardrails import RailsConfig, LLMRails
        from preflight.guardrails.rails import GuardrailResult, GuardrailAction

        rails_config = RailsConfig.from_content(
            config_content=COLANG_CONFIG_YAML,
            colang_content=COLANG_FLOWS + COLANG_DEFINITIONS,
        )

        rails = LLMRails(rails_config)

        request_type = getattr(context, "request_type", "unknown")
        impact_level = getattr(context, "impact_level", "medium")
        has_patient_data = getattr(context, "has_patient_data", False)
        has_clinical_system = getattr(context, "has_clinical_system", False)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Preflight assessment: request_type={request_type}, "
                    f"impact_level={impact_level}, "
                    f"has_patient_data={has_patient_data}, "
                    f"has_clinical_system={has_clinical_system}"
                ),
            }
        ]

        result = rails.generate(messages=messages)

        content = result.get("content", "") if isinstance(result, dict) else str(result)
        is_block = "block" in content.lower() or "cannot" in content.lower()
        is_escalate = "escalate" in content.lower() or "sign-off" in content.lower()
        is_warn = "warning" in content.lower() or "flag" in content.lower()

        if is_block:
            return GuardrailResult(
                passed=False,
                rail_name="nemo_supplementary",
                reason=f"NeMo Guardrails supplementary check: {content[:200]}",
                action=GuardrailAction.BLOCK.value,
                metadata={"nemo_content": content[:500]},
            )
        elif is_escalate:
            return GuardrailResult(
                passed=False,
                rail_name="nemo_supplementary",
                reason=f"NeMo Guardrails escalation: {content[:200]}",
                action=GuardrailAction.ESCALATE.value,
                metadata={"nemo_content": content[:500]},
            )
        elif is_warn:
            return GuardrailResult(
                passed=True,
                rail_name="nemo_supplementary",
                reason=f"NeMo Guardrails warning: {content[:200]}",
                action=GuardrailAction.WARN.value,
                metadata={"nemo_content": content[:500]},
            )

        return None

    except ImportError:
        logger.debug("nemoguardrails not installed — supplementary check skipped")
        return None
    except Exception as exc:
        logger.warning(f"NeMo Guardrails supplementary check failed: {exc}")
        return None


def write_colang_files(output_dir: str | Path | None = None) -> Path:
    """Write Colang configuration files to disk for NeMo Guardrails.

    This is useful if you want to run NeMo Guardrails as a standalone service
    rather than embedded in the Python process.
    """
    output = Path(output_dir) if output_dir else COLANG_DIR
    output.mkdir(parents=True, exist_ok=True)

    config_path = output / "config.yml"
    config_path.write_text(COLANG_CONFIG_YAML, encoding="utf-8")

    flows_path = output / "flows.co"
    flows_path.write_text(COLANG_FLOWS, encoding="utf-8")

    definitions_path = output / "definitions.co"
    definitions_path.write_text(COLANG_DEFINITIONS, encoding="utf-8")

    logger.info(f"Colang files written to {output}")
    return output
