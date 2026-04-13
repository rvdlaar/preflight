"""
Preflight guardrail hook registry — extensible pre/post processing hooks.

FIRST PRINCIPLE: Guardrails are NOT just regex filters. They are a PLUGGABLE
REGISTRY of checks that run at defined points in the pipeline. Different hooks
for different contexts: BSN detection before assessment, NEN 7513 audit after
authority outputs, PII stripping for external documents.

SECOND ORDER: If hooks are hard to register, nobody adds them. If hooks can
modify output silently, we lose auditability. Solution: hooks return HookResult
with modified text AND a flag log — every hook action is auditable.

INVERSION: What makes guardrails dangerous? Over-blocking. Victor MUST be able
to say "this system has no SBOM" — that's not an injection, that's a finding.
Authority persona outputs are NEVER filtered. The registry enforces this with
the skip_authority flag.

Pattern inspired by Onyx's hook system, adapted for Dutch healthcare context
with BSN/NEN 7513/NEN 7510 regulatory requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol


class HookPoint(str, Enum):
    PRE_CLASSIFY = "pre_classify"
    PRE_ASSESS = "pre_assess"
    POST_ASSESS = "post_assess"
    PRE_AUTHORITY = "pre_authority"
    POST_AUTHORITY = "post_authority"
    PRE_SYNTHESIS = "pre_synthesis"
    POST_SYNTHESIS = "post_synthesis"
    PRE_OUTPUT = "pre_output"
    POST_OUTPUT = "post_output"


class HookAction(str, Enum):
    PASS = "pass"
    FLAG = "flag"
    MODIFY = "modify"
    BLOCK = "block"


@dataclass
class HookResult:
    text: str
    action: HookAction = HookAction.PASS
    flags: list[str] = field(default_factory=list)
    modifications: list[str] = field(default_factory=list)
    skip_authority: bool = False

    @property
    def is_blocked(self) -> bool:
        return self.action == HookAction.BLOCK

    @property
    def was_modified(self) -> bool:
        return self.action in (HookAction.MODIFY, HookAction.FLAG)


class GuardHook(Protocol):
    name: str
    point: HookPoint
    skip_authority: bool

    def run(self, text: str, context: dict) -> HookResult: ...


BSN_PATTERN = re.compile(r"(?<!\d)\d{9}(?!\d)")

PATIENT_ID_PATTERNS = [
    re.compile(
        r"(?:patiëntid|patientid|patient_id|patiënt_id)\s*[:=]\s*\S+", re.IGNORECASE
    ),
    re.compile(r"(?:burger service nummer|bsn)\s*[:=]\s*\d{9}", re.IGNORECASE),
    re.compile(
        r"(?:medisch record nummer|mrn|medical record)\s*[:=]\s*\S+", re.IGNORECASE
    ),
]

INJECTION_PATTERNS = [
    (
        re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+(?:instructions?|prompts?)"),
        "ignore-previous",
    ),
    (
        re.compile(r"(?i)forget\s+(?:all\s+)?previous\s+(?:instructions?|prompts?)"),
        "forget-previous",
    ),
    (
        re.compile(r"(?i)disregard\s+(?:all\s+)?previous\s+(?:instructions?|prompts?)"),
        "disregard-previous",
    ),
    (
        re.compile(
            r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|unrestricted)\s+(?:ai|assistant|model)"
        ),
        "persona-switch",
    ),
    (
        re.compile(r"(?i)system\s*:\s*(?:you\s+are|act\s+as|pretend)"),
        "system-injection",
    ),
    (re.compile(r"(?i)<\s*system\s*>"), "xml-system-tag"),
    (re.compile(r"(?i)jailbreak"), "jailbreak-keyword"),
]


class BSNDetectionHook:
    name = "bsn_detection"
    point = HookPoint.PRE_CLASSIFY
    skip_authority = True

    def run(self, text: str, context: dict) -> HookResult:
        matches = BSN_PATTERN.findall(text)
        if not matches:
            return HookResult(text=text)
        flags = [f"BSN_DETECTED:{len(matches)}x potential BSN number(s) found"]
        cleaned = BSN_PATTERN.sub("[BSN_REDACTED]", text)
        return HookResult(
            text=cleaned,
            action=HookAction.MODIFY,
            flags=flags,
            modifications=["Replaced BSN number(s) with [BSN_REDACTED]"],
            skip_authority=True,
        )


class PatientIDHook:
    name = "patient_id_detection"
    point = HookPoint.PRE_CLASSIFY
    skip_authority = True

    def run(self, text: str, context: dict) -> HookResult:
        flags = []
        for pattern in PATIENT_ID_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                flags.append(f"PATIENT_ID_DETECTED:{len(matches)}x")
        if not flags:
            return HookResult(text=text)
        cleaned = text
        for pattern in PATIENT_ID_PATTERNS:
            cleaned = pattern.sub("[PATIENT_ID_REDACTED]", cleaned)
        return HookResult(
            text=cleaned,
            action=HookAction.FLAG,
            flags=flags,
            modifications=["Redacted patient identifiers"],
            skip_authority=True,
        )


class InjectionDetectionHook:
    name = "injection_detection"
    point = HookPoint.PRE_ASSESS
    skip_authority = True

    def run(self, text: str, context: dict) -> HookResult:
        flags = []
        threat_level = HookAction.PASS
        clean = text

        for pattern, flag_name in INJECTION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                flags.append(f"injection:{flag_name}:{len(matches)}x")
                if threat_level == HookAction.PASS:
                    threat_level = HookAction.FLAG

        for pattern, flag_name in [
            (
                re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE),
                "script-tag",
            ),
            (
                re.compile(r"<iframe[^>]*>.*?</iframe>", re.DOTALL | re.IGNORECASE),
                "iframe-tag",
            ),
            (re.compile(r"javascript\s*:", re.IGNORECASE), "javascript-protocol"),
        ]:
            matches = pattern.findall(text)
            if matches:
                flags.append(f"executable:{flag_name}:{len(matches)}x")
                threat_level = HookAction.MODIFY
                clean = pattern.sub(f"[{flag_name} removed]", clean)

        return HookResult(
            text=clean,
            action=threat_level,
            flags=flags,
            skip_authority=True,
        )


class NEN7513AuditHook:
    name = "nen7513_audit"
    point = HookPoint.POST_OUTPUT
    skip_authority = False

    def run(self, text: str, context: dict) -> HookResult:
        assessment_id = context.get("assessment_id", "unknown")
        user_id = context.get("user_id", "unknown")
        flags = []
        flags.append(f"NEN_7513_AUDIT:assessment_id={assessment_id}")
        flags.append(f"NEN_7513_AUDIT:user_id={user_id}")
        flags.append(f"NEN_7513_AUDIT:output_length={len(text)}")
        if "[BSN_REDACTED]" in text:
            flags.append("NEN_7513_AUDIT:bsn_redacted_in_output=True")
        return HookResult(text=text, action=HookAction.FLAG, flags=flags)


class GuardrailRegistry:
    """Registry of guardrail hooks that run at defined pipeline points.

    Authority persona outputs (VETO, ESCALATION, INDEPENDENT, CHALLENGE,
    PATIENT_SAFETY) are NEVER modified — only flagged. This is a hard rule
    because suppressing a security VETO or DPO DETERMINATION is a safety failure.
    """

    def __init__(self):
        self._hooks: dict[HookPoint, list[GuardHook]] = {
            point: [] for point in HookPoint
        }

    def register(self, hook: GuardHook) -> None:
        self._hooks[hook.point].append(hook)

    def run_hooks(
        self,
        point: HookPoint,
        text: str,
        context: dict | None = None,
        is_authority: bool = False,
    ) -> HookResult:
        context = context or {}
        hooks = self._hooks.get(point, [])
        current = HookResult(text=text)
        all_flags: list[str] = []

        for hook in hooks:
            if is_authority and hook.skip_authority:
                all_flags.append(
                    f"SKIPPED_HOOK:{hook.name}(authority_output_protected)"
                )
                continue

            result = hook.run(current.text, context)

            if result.action == HookAction.BLOCK:
                return HookResult(
                    text=result.text,
                    action=HookAction.BLOCK,
                    flags=all_flags + result.flags,
                    modifications=current.modifications + result.modifications,
                )

            current.text = result.text
            all_flags.extend(result.flags)
            current.modifications.extend(result.modifications)

        current.flags = all_flags
        return current


def create_default_registry() -> GuardrailRegistry:
    registry = GuardrailRegistry()
    registry.register(BSNDetectionHook())
    registry.register(PatientIDHook())
    registry.register(InjectionDetectionHook())
    registry.register(NEN7513AuditHook())
    return registry
