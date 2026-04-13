"""
Step 1: Classify — determine request type + impact level from a business request.

Drives persona selection, triage floors, and required document set.
"""

from preflight.classify.classify import (
    classify_request,
    classify_request_dual,
    ClassificationResult,
    DualClassificationResult,
    REQUEST_TYPES,
    IMPACT_LEVELS,
    ROUTING,
    CORE_ALWAYS,
    select_relevant_perspectives,
    _heuristic_classify,
)

__all__ = [
    "classify_request",
    "classify_request_dual",
    "ClassificationResult",
    "DualClassificationResult",
    "REQUEST_TYPES",
    "IMPACT_LEVELS",
    "ROUTING",
    "CORE_ALWAYS",
    "select_relevant_perspectives",
]
