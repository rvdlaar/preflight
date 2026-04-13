"""
Preflight citation verification — extract, verify, and score citations in LLM output.

Design decisions:
- All regulatory citations must exist in the knowledge base
- Confidence scores are per-finding, not per-assessment
- Authority persona outputs (VETO, ESCALATION, INDEPENDENT) require N>=2 sources per claim
- Unverified citations get [VERIFY] markers — not silently removed
- The verification result is stored for audit trail (NEN 7513)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class CitationType(str, Enum):
    PERSONA = "persona"
    KNOWLEDGE = "knowledge"
    VERIFY = "verify"
    UNKNOWN = "unknown"


@dataclass
class Citation:
    raw: str
    citation_type: CitationType
    source_id: str
    start_pos: int
    end_pos: int
    verified: bool = False
    verification_failure: str = ""


@dataclass
class Claim:
    text: str
    citations: list[Citation] = field(default_factory=list)
    verified: bool = False
    needs_review: bool = False


@dataclass
class CitationReport:
    total_citations: int = 0
    verified_citations: int = 0
    unverified_citations: int = 0
    verify_markers: int = 0
    faithfulness_score: float = 0.0
    claims: list[Claim] = field(default_factory=list)
    citations_detail: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return self.faithfulness_score >= 0.8


CITATION_PERSONA_RE = re.compile(r"\[§P:([^\]]+)\]")
CITATION_KNOWLEDGE_RE = re.compile(r"\[§K:([^\]]+)\]")
VERIFY_MARKER_RE = re.compile(r"\[VERIFY\]")

REGULATORY_ID_RE = re.compile(
    r"\b("
    r"NEN\s+\d{4}(?:[-/]\d+)?(?:\s+[A-Z]\.\d+(?:\.\d+)*)?"
    r"|ISO\s+\d+(?:[-/]\d+)?(?:\s+[A-Z]\.\d+)?"
    r"|AVG\s+(?:Art\.?|artikel)\s+\d+"
    r"|GDPR\s+(?:Art\.?|Article)\s+\d+"
    r"|AIVG\s+\d{4}"
    r"|NIS2(?:\s+Art\.?\s+\d+)?"
    r"|MDR\s+(?:Art\.?|Article)\s+\d+"
    r"|IVDR\s+(?:Art\.?|Article)\s+\d+"
    r"|WGBO\s+(?:Art\.?|artikel)\s+\d+"
    r"|UWPG\s+(?:Art\.?|artikel)\s+\d+"
    r"|Wegiz(?:\s+Art\.?|artikel)?\s*\d*"
    r"|EU\s+AI\s+Act(?:\s+Art\.?\s+\d+)?"
    r")",
    re.IGNORECASE,
)


def extract_citations(text: str) -> list[Citation]:
    """Extract all citations from LLM output text."""
    citations: list[Citation] = []

    for match in CITATION_PERSONA_RE.finditer(text):
        citations.append(
            Citation(
                raw=match.group(0),
                citation_type=CitationType.PERSONA,
                source_id=match.group(1),
                start_pos=match.start(),
                end_pos=match.end(),
            )
        )

    for match in CITATION_KNOWLEDGE_RE.finditer(text):
        citations.append(
            Citation(
                raw=match.group(0),
                citation_type=CitationType.KNOWLEDGE,
                source_id=match.group(1),
                start_pos=match.start(),
                end_pos=match.end(),
            )
        )

    for match in VERIFY_MARKER_RE.finditer(text):
        citations.append(
            Citation(
                raw=match.group(0),
                citation_type=CitationType.VERIFY,
                source_id="VERIFY",
                start_pos=match.start(),
                end_pos=match.end(),
                verified=False,
            )
        )

    return citations


def extract_regulatory_references(text: str) -> list[str]:
    """Extract regulatory article/control references from LLM output.

    These are the dangerous ones — hallucinated NEN 7510 clauses,
    GDPR articles that don't exist, etc.
    """
    return [m.group(1).strip() for m in REGULATORY_ID_RE.finditer(text)]


def verify_citations(
    citations: list[Citation],
    known_personas: list[str] | None = None,
    known_sources: set[str] | None = None,
    retrieved_source_ids: list[str] | None = None,
) -> list[Citation]:
    """Verify citations against known personas, knowledge base sources, and retrieved context.

    - Persona citations: verified if the persona name exists in known_personas
    - Knowledge citations: verified if the source_id exists in the knowledge base
    - Knowledge citations in assessment: also checked against retrieved context
    - [VERIFY] markers: always unverified (that's the point)
    """
    known_persona_set = set(known_personas or [])
    known_source_set = known_sources or set()
    retrieved_set = set(retrieved_source_ids or [])

    for cit in citations:
        if cit.citation_type == CitationType.VERIFY:
            cit.verified = False
            cit.verification_failure = "Explicit VERIFY marker — requires human review"
            continue

        if cit.citation_type == CitationType.PERSONA:
            if cit.source_id in known_persona_set:
                cit.verified = True
            else:
                cit.verified = False
                cit.verification_failure = (
                    f"Persona '{cit.source_id}' not found in known persona definitions"
                )
            continue

        if cit.citation_type == CitationType.KNOWLEDGE:
            if cit.source_id in known_source_set:
                cit.verified = True
                if retrieved_set and cit.source_id not in retrieved_set:
                    cit.verification_failure = (
                        f"Source '{cit.source_id}' exists in knowledge base but "
                        f"was NOT in the retrieved context for this assessment. "
                        f"Verify the finding is still supported."
                    )
            else:
                if retrieved_set and cit.source_id in retrieved_set:
                    cit.verified = True
                else:
                    cit.verified = False
                    cit.verification_failure = (
                        f"Source '{cit.source_id}' not found in knowledge base "
                        f"or retrieved context"
                    )
            continue

        cit.verified = False
        cit.verification_failure = "Unknown citation type"

    return citations


def verify_regulatory_references(
    references: list[str],
    known_regulatory_ids: set[str] | None = None,
) -> list[tuple[str, bool, str]]:
    """Verify regulatory references against the knowledge base.

    Returns list of (reference, is_verified, explanation).
    This is the hallucination mitigation layer from ARCHITECTURE.md.
    """
    known = known_regulatory_ids or set()
    results: list[tuple[str, bool, str]] = []

    for ref in references:
        if ref in known:
            results.append((ref, True, "Found in knowledge base"))
        else:
            normalized = _normalize_regulatory_id(ref)
            found = False
            for known_ref in known:
                if _normalize_regulatory_id(known_ref) == normalized:
                    found = True
                    results.append((ref, True, f"Matches known reference: {known_ref}"))
                    break
            if not found:
                results.append(
                    (
                        ref,
                        False,
                        f"⚠ Unverified reference: {ref} — not found in knowledge base. "
                        f"Verify before relying on this finding.",
                    )
                )

    return results


def build_citation_report(
    persona_findings: list[dict],
    known_personas: list[str] | None = None,
    known_sources: set[str] | None = None,
    retrieved_source_ids: list[str] | None = None,
    known_regulatory_ids: set[str] | None = None,
    authority_persona_ids: list[str] | None = None,
) -> CitationReport:
    """Build a full citation report across all persona findings.

    This produces the verification data stored alongside the assessment
    for audit trail and board review.
    """
    authority_ids = set(authority_persona_ids or ["security", "risk", "fg-dpo", "cmio"])

    all_citations: list[Citation] = []
    all_claims: list[Claim] = []
    all_warnings: list[str] = []

    for finding in persona_findings:
        findings_text = finding.get("findings", "")
        if isinstance(findings_text, list):
            findings_text = " ".join(str(f) for f in findings_text)

        conditions_text = finding.get("conditions", "")
        if isinstance(conditions_text, list):
            conditions_text = " ".join(str(c) for c in conditions_text)

        text_to_check = f"{findings_text} {conditions_text}"

        if not text_to_check.strip():
            continue

        citations = extract_citations(text_to_check)
        citations = verify_citations(
            citations, known_personas, known_sources, retrieved_source_ids
        )
        all_citations.extend(citations)

        reg_refs = extract_regulatory_references(text_to_check)
        if reg_refs:
            reg_results = verify_regulatory_references(reg_refs, known_regulatory_ids)
            for ref, verified, explanation in reg_results:
                if not verified:
                    all_warnings.append(
                        f"[{finding.get('perspective_id', '?')}] {explanation}"
                    )

        perspective_id = finding.get("perspective_id", "")
        is_authority = perspective_id in authority_ids

        unverified = [c for c in citations if not c.verified]

        claim = Claim(
            text=text_to_check[:200],
            citations=citations,
            verified=len(unverified) == 0,
            needs_review=bool(unverified) or is_authority,
        )

        if is_authority and verified_count(citations) < 2 and citations:
            claim.needs_review = True
            all_warnings.append(
                f"Authority persona '{perspective_id}' finding has fewer than "
                f"2 verified source citations — requires mandatory review"
            )

        all_claims.append(claim)

    total = len(all_citations)
    verified = verified_count(all_citations)
    unverified = total - verified
    verify_markers = sum(
        1 for c in all_citations if c.citation_type == CitationType.VERIFY
    )

    faithfulness = verified / total if total > 0 else 1.0

    return CitationReport(
        total_citations=total,
        verified_citations=verified,
        unverified_citations=unverified,
        verify_markers=verify_markers,
        faithfulness_score=round(faithfulness, 3),
        claims=all_claims,
        citations_detail=all_citations,
        warnings=all_warnings,
    )


def annotate_output_with_verify(text: str, report: CitationReport) -> str:
    """Annotate LLM output with [VERIFY] markers for unverified claims.

    Adds warning annotations after lines containing unverified citations.
    """
    if report.is_acceptable and not report.warnings:
        return text

    lines = text.split("\n")
    annotated_lines: list[str] = []

    for line in lines:
        annotated_lines.append(line)

        for cit in report.citations_detail:
            if not cit.verified and cit.raw in line:
                annotated_lines.append(
                    f"> ⚠ **UNVERIFIED CITATION**: `{cit.raw}` — "
                    f"{cit.verification_failure}"
                )

    unverified_refs = [(r, v, e) for r, v, e in _collect_reg_warnings(report) if not v]
    for ref, verified, explanation in unverified_refs:
        if ref in line:
            annotated_lines.append(f"> ⚠ **{explanation}**")

    return "\n".join(annotated_lines)


def verified_count(citations: list[Citation]) -> int:
    return sum(1 for c in citations if c.verified)


def _normalize_regulatory_id(ref: str) -> str:
    """Normalize regulatory ID for fuzzy matching."""
    normalized = re.sub(r"\s+", " ", ref.strip())
    normalized = re.sub(r"[./]", "-", normalized)
    return normalized.upper()


def _collect_reg_warnings(report: CitationReport) -> list[tuple[str, bool, str]]:
    """Extract regulatory reference warnings from a citation report."""
    results: list[tuple[str, bool, str]] = []
    seen: set[str] = set()
    for claim in report.claims:
        for cit in claim.citations:
            if cit.verification_failure and cit.raw not in seen:
                seen.add(cit.raw)
                results.append((cit.raw, cit.verified, cit.verification_failure))
    for warning in report.warnings:
        if warning not in seen:
            seen.add(warning)
            results.append((warning, False, warning))
    return results
