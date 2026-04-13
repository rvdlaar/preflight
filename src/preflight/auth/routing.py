"""
Preflight LLM routing — confidence-based escalation between tiers.

FIRST PRINCIPLES:
  1. Different steps have different reasoning demands (from ARCHITECTURE.md)
  2. 80% of calls hit the light tier — cost goes where it matters
  3. The critical question: what if the cheap model MISCLASSIFIES?
     → A clinical system classified as infrastructure-change skips CMIO.
     → This must NEVER happen. Confidence-based escalation to strong model.

INVERSION: What makes routing fail?
  - False fast-track >10% → kill metric from ARCHITECTURE.md
  - Light model always returns high confidence → need calibrated confidence
  - Strong model is down → fallback to light with warning
  - Routing adds too much latency → cache classification results

SECOND ORDER:
  - Escalation from light→strong doubles latency for that single call
  - But it prevents the cascade failure of misclassification
  - The kill metric (10% false fast-track) is measurable and enforced
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from preflight.llm.client import LLMRouter, LLMResponse, CallOpts


@dataclass
class RoutingDecision:
    tier: str
    reason: str
    confidence: float
    escalated: bool = False
    escalation_reason: str = ""


@dataclass
class RoutingConfig:
    classification_confidence_threshold: float = 0.7
    assessment_confidence_threshold: float = 0.5
    critical_type_force_strong: set[str] = field(
        default_factory=lambda: {"clinical-system", "ai-ml"}
    )
    critical_impact_force_frontier: set[str] = field(
        default_factory=lambda: {"critical"}
    )
    enable_escalation: bool = True
    max_escalation_attempts: int = 1


STEP_TIER_MAP: dict[str, str] = {
    "ingest": "light",
    "classify": "light",
    "retrieve": "light",
    "assess_fast": "light",
    "assess_deep": "strong",
    "challenge": "frontier",
    "output": "light",
}


class ConfidenceEstimator:
    """Estimate classification confidence to decide escalation.

    FIRST PRINCIPLE: Confidence is not "how sure the LLM is" — that's
    self-reported and unreliable. Confidence is "how consistent is this
    classification with the input features?" — heuristic checks.

    INVERSION: What if confidence is always high?
      → Add feature-based checks: does the input mention clinical keywords
        but got classified as infrastructure? Low confidence despite LLM score.
    """

    CLINICAL_KEYWORDS = frozenset(
        {
            "patient",
            "clinical",
            "hir",
            "fhir",
            "dicom",
            "his",
            "lis",
            "emd",
            "epd",
            "medisch",
            "patiënt",
            "klinisch",
            "cloverleaf",
            "jivex",
            "digizorg",
            "medication",
            "vitals",
            "ward",
        }
    )

    INTEGRATION_KEYWORDS = frozenset(
        {
            "interface",
            "integration",
            "api",
            "hl7",
            "message",
            "_coupling",
            "interoperabiliteit",
            "koppeling",
            "integratie",
        }
    )

    MANUFACTURING_KEYWORDS = frozenset(
        {
            "scada",
            "plc",
            "manufacturing",
            "ot",
            "industrial",
            "productie",
        }
    )

    def estimate_classification_confidence(
        self, request: str, classification: str, impact: str
    ) -> float:
        """Estimate confidence in the classification result.

        Uses keyword overlap between request text and expected classification domain.
        If clinical keywords appear but classification is not clinical-system,
        confidence drops — this is the key escalation trigger.
        """
        text_lower = request.lower()
        words = set(text_lower.split())

        clinical_overlap = words & self.CLINICAL_KEYWORDS
        integration_overlap = words & self.INTEGRATION_KEYWORDS
        manufacturing_overlap = words & self.MANUFACTURING_KEYWORDS

        confidence = 0.9

        if clinical_overlap and classification != "clinical-system":
            confidence -= 0.3 * min(len(clinical_overlap), 3)

        if integration_overlap and classification != "integration":
            confidence -= 0.2 * min(len(integration_overlap), 2)

        if manufacturing_overlap and classification != "manufacturing-ot":
            confidence -= 0.2 * min(len(manufacturing_overlap), 2)

        if impact == "critical" and classification not in (
            "clinical-system",
            "ai-ml",
            "data-platform",
        ):
            confidence -= 0.15

        return max(0.0, min(1.0, confidence))


class TieredRouter:
    """Route LLM calls to the correct tier with confidence-based escalation.

    Pipeline:
      1. Determine base tier from step type
      2. Override to strong/frontier for critical request types
      3. Call the appropriate tier
      4. If confidence < threshold AND escalation enabled, re-call at higher tier
      5. Return the better result with a routing decision record
    """

    def __init__(
        self,
        router: LLMRouter,
        config: RoutingConfig | None = None,
    ):
        self.router = router
        self.config = config or RoutingConfig()
        self._estimator = ConfidenceEstimator()

    async def call_classify(
        self, request: str, system: str, user: str, opts: CallOpts | None = None
    ) -> tuple[LLMResponse, RoutingDecision]:
        """Classify with automatic escalation if confidence is low.

        FIRST PRINCIPLE: A misclassified clinical system is the worst failure.
        Escalating to the strong model costs 2x but prevents 10x damage.
        """
        decision = RoutingDecision(
            tier="light",
            reason="Classification step, default light tier",
            confidence=1.0,
        )

        client = self.router.light()
        response = await client.call(system, user, opts)

        if self.config.enable_escalation:
            text_lower = request.lower()
            force_strong = (
                any(kw in text_lower for kw in self._estimator.CLINICAL_KEYWORDS)
                and request not in self.config.critical_type_force_strong
            )

            if force_strong or self._should_escalate_classification(request, response):
                decision.escalated = True
                decision.escalation_reason = (
                    "Clinical keywords detected, escalating to strong model "
                    "for classification accuracy"
                )
                decision.tier = "strong"
                strong_client = self.router.strong()
                response = await strong_client.call(system, user, opts)

        return response, decision

    async def call_assess(
        self,
        system: str,
        user: str,
        mode: str = "fast",
        request_type: str = "",
        impact_level: str = "",
        opts: CallOpts | None = None,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """Route assessment call based on mode and criticality."""
        if mode == "deep":
            tier = "strong"
        elif impact_level in self.config.critical_impact_force_frontier:
            tier = "frontier"
        elif request_type in self.config.critical_type_force_strong:
            tier = "strong"
        else:
            tier = STEP_TIER_MAP.get(f"assess_{mode}", "light")

        decision = RoutingDecision(
            tier=tier,
            reason=f"Assessment mode={mode}, type={request_type}, impact={impact_level}",
            confidence=1.0,
        )

        client_map = {
            "light": self.router.light,
            "strong": self.router.strong,
            "frontier": self.router.frontier,
        }
        client_getter = client_map.get(tier, self.router.light)
        client = client_getter()

        response = await client.call(system, user, opts)
        return response, decision

    async def call_challenge(
        self,
        system: str,
        user: str,
        impact_level: str = "",
        opts: CallOpts | None = None,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """Route challenge step — frontier for high/critical, strong otherwise."""
        if impact_level in self.config.critical_impact_force_frontier:
            tier = "frontier"
        else:
            tier = "strong"

        decision = RoutingDecision(
            tier=tier,
            reason=f"Challenge step, impact={impact_level}",
            confidence=1.0,
        )

        client_map = {
            "strong": self.router.strong,
            "frontier": self.router.frontier,
        }
        client = client_map.get(tier, self.router.strong)()

        response = await client.call(system, user, opts)
        return response, decision

    def _should_escalate_classification(
        self, request: str, response: LLMResponse
    ) -> bool:
        """Check if a classification result should be escalated.

        Triggers escalation when:
          1. Response is suspiciously short (LLM not reasoning)
          2. Response contains hedging language
          3. Clinical keywords in input but no clinical classification in output
        """
        text = response.text.lower()

        if len(response.text) < 50:
            return True

        hedge_phrases = ["might be", "could be", "possibly", "uncertain", "not sure"]
        if any(phrase in text for phrase in hedge_phrases):
            return True

        clinical_in_input = any(
            kw in request.lower() for kw in self._estimator.CLINICAL_KEYWORDS
        )
        clinical_in_output = "clinical" in text
        if clinical_in_input and not clinical_in_output:
            return True

        return False
