"""
Preflight citation module — verification, extraction, grounding checks,
and 3-mode citation processing with cross-persona accumulation.

Citation format (from ARCHITECTURE.md):
  [§P:PersonaName] — claims from persona expertise
  [§K:source-id]    — claims from knowledge base
  [VERIFY]          — unverified claims requiring human review

Citation processing modes:
  HYPERLINK    — for final PSA/ADR output with source links
  KEEP_MARKERS — for intermediate persona assessments (preserves [§K:] markers)
  REMOVE       — for authority persona outputs (VETO/ESCALATION/INDEPENDENT)
"""

from preflight.citation.verify import (
    verify_citations,
    build_citation_report,
    CitationReport,
    Citation,
    CitationType,
    Claim,
)
from preflight.citation.processor import (
    CitationProcessor,
    CitationMapping,
    CitationMode,
    CitationInfo,
    SourceDoc,
)

__all__ = [
    "verify_citations",
    "build_citation_report",
    "CitationReport",
    "Citation",
    "CitationType",
    "Claim",
    "CitationProcessor",
    "CitationMapping",
    "CitationMode",
    "CitationInfo",
    "SourceDoc",
]
