"""
Preflight structured output parser — LLM response → ratings + findings.

This is defensive code. LLMs will surprise you.
Parse conservatively, handle edge cases, never crash on malformed input.

Design decisions:
- Parse delimited sections, not JSON — LLMs are better at formatting text than JSON
- Multiple fallback strategies: strict → relaxed → regex extraction
- Every parsed finding must link back to a perspective_id
- If parsing fails completely, return raw text with a flag for human review
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Parsed output types
# ---------------------------------------------------------------------------


@dataclass
class ParsedRating:
    perspective_id: str
    rating: str  # approve | conditional | concern | block | na
    reason: str = ""
    conditions: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return self.rating in {"approve", "conditional", "concern", "block", "na"}


@dataclass
class ParsedDeepResult:
    perspective_id: str
    rating: str
    findings: list[str] = field(default_factory=list)
    strongest_objection: str = ""
    hidden_concern: str = ""
    conditions: list[str] = field(default_factory=list)
    rating_change_trigger: str = ""
    authority: str | None = None


@dataclass
class ParseResult:
    ratings: list[ParsedRating] = field(default_factory=list)
    unparsed: str = ""
    parse_confidence: float = 0.0  # 0-1: how confident are we in this parse


VALID_RATINGS = {"approve", "conditional", "concern", "block", "na"}

# Common LLM formatting errors we handle
RATING_ALIASES = {
    "accepted": "approve",
    "accept": "approve",
    "ok": "approve",
    "yes": "approve",
    "approved": "approve",
    "flag": "concern",
    "worried": "concern",
    "caution": "concern",
    "warning": "concern",
    "reject": "block",
    "rejected": "block",
    "veto": "block",
    "block": "block",
    "stop": "block",
    "n/a": "na",
    "not applicable": "na",
    "not relevant": "na",
    "skip": "na",
}


# ---------------------------------------------------------------------------
# Fast mode parser — batched ratings
# ---------------------------------------------------------------------------


def parse_fast_assessment(text: str) -> ParseResult:
    """Parse a batched fast-mode LLM response.

    Tries strategies in order:
    1. Delimited section parsing (strict)
    2. Inline format parsing (relaxed)
    3. Regex extraction (last resort)
    """
    # Strategy 1: Delimited sections
    result = _parse_delimited(text)
    if result.ratings and result.parse_confidence >= 0.7:
        return result

    # Strategy 2: Inline format "cio:conditional chief:approve security:concern"
    result = _parse_inline(text)
    if result.ratings and result.parse_confidence >= 0.5:
        return result

    # Strategy 3: Regex extraction — find any rating-like patterns
    result = _parse_regex(text)
    if result.ratings:
        return result

    # Complete failure — return raw text for human review
    return ParseResult(
        ratings=[],
        unparsed=text,
        parse_confidence=0.0,
    )


def _parse_delimited(text: str) -> ParseResult:
    ratings = []
    findings = {}
    conditions = {}

    # Extract ratings section
    ratings_match = re.search(
        r"\[PERSPECTIVE_RATINGS\]\s*(.*?)\s*\[/PERSPECTIVE_RATINGS\]", text, re.DOTALL
    )
    if not ratings_match:
        return ParseResult(parse_confidence=0.0)

    # Parse ratings line: "cio:conditional chief:approve security:concern"
    ratings_text = ratings_match.group(1).strip()
    for pair in re.findall(r"(\w[\w-]*):(\w+)", ratings_text):
        pid, raw_rating = pair
        rating = _normalize_rating(raw_rating)
        if rating:
            ratings.append(ParsedRating(perspective_id=pid, rating=rating))

    # Extract findings section
    findings_match = re.search(
        r"\[PERSPECTIVE_FINDINGS\]\s*(.*?)\s*\[/PERSPECTIVE_FINDINGS\]", text, re.DOTALL
    )
    if findings_match:
        for line in findings_match.group(1).strip().splitlines():
            m = re.match(r"(\w[\w-]*):\s*(.+)", line.strip())
            if m:
                findings[m.group(1)] = m.group(2).strip()

    # Extract conditions section
    conditions_match = re.search(
        r"\[PERSPECTIVE_CONDITIONS\]\s*(.*?)\s*\[/PERSPECTIVE_CONDITIONS\]",
        text,
        re.DOTALL,
    )
    if conditions_match:
        for line in conditions_match.group(1).strip().splitlines():
            m = re.match(r"(\w[\w-]*):\s*(.+)", line.strip())
            if m:
                pid = m.group(1)
                cond_text = m.group(2).strip()
                if cond_text.lower() not in ("none", "n/a", "geen", "-"):
                    conditions[pid] = [c.strip() for c in cond_text.split(",")]

    # Merge findings and conditions into ratings
    for r in ratings:
        r.reason = findings.get(r.perspective_id, "")
        r.conditions = conditions.get(r.perspective_id, [])

    confidence = (
        len(ratings) / max(len(re.findall(r"(\w[\w-]*):(\w+)", ratings_text)), 1)
        if ratings
        else 0.0
    )
    return ParseResult(
        ratings=ratings, unparsed="", parse_confidence=min(confidence, 1.0)
    )


def _parse_inline(text: str) -> ParseResult:
    """Parse inline format: [1] cio:conditional chief:approve security:concern"""
    ratings = []

    # Find the numbered line with ratings
    for line in text.splitlines():
        m = re.match(r"\[[\d]+\]\s*(.+)", line.strip())
        if m:
            for pair in re.findall(r"(\w[\w-]*):(\w+)", m.group(1)):
                pid, raw_rating = pair
                rating = _normalize_rating(raw_rating)
                if rating:
                    ratings.append(ParsedRating(perspective_id=pid, rating=rating))
            if ratings:
                break

    # Try to find per-perspective reasons in subsequent lines
    finding_lines = []
    in_findings = False
    for line in text.splitlines():
        m = re.match(r"(\w[\w-]*):\s*(.+)", line.strip())
        if m and m.group(1) in {r.perspective_id for r in ratings}:
            finding_lines.append((m.group(1), m.group(2).strip()))

    for r in ratings:
        for pid, reason in finding_lines:
            if pid == r.perspective_id and not r.reason:
                r.reason = reason

    confidence = 0.6 if ratings else 0.0
    return ParseResult(ratings=ratings, unparsed="", parse_confidence=confidence)


def _parse_regex(text: str) -> ParseResult:
    """Last resort: find any rating-like pattern anywhere in text."""
    ratings = []
    seen = set()

    # Look for "perspective_id: rating" pairs anywhere
    for m in re.finditer(r"(\w[\w-]*)\s*:\s*(\w+)", text):
        pid, raw = m.group(1), m.group(2)
        rating = _normalize_rating(raw)
        if rating and pid not in seen:
            seen.add(pid)
            ratings.append(ParsedRating(perspective_id=pid, rating=rating))

    return ParseResult(ratings=ratings, unparsed=text, parse_confidence=0.3)


# ---------------------------------------------------------------------------
# Deep mode parser — single persona structured output
# ---------------------------------------------------------------------------


def parse_deep_assessment(text: str, perspective_id: str) -> ParsedDeepResult:
    """Parse a deep-mode single-persona response with delimited sections."""

    rating = _extract_section(text, "MY_RATING", default="conditional")
    rating = (
        _normalize_rating(rating.strip().split("\n")[0].strip().lower())
        or "conditional"
    )

    findings_text = _extract_section(text, "FINDINGS", default="")
    findings = [
        line.lstrip("- ").strip()
        for line in findings_text.splitlines()
        if line.strip() and line.strip() != "-"
    ]

    objection = _extract_section(text, "STRONGEST_OBJECTION", default="")
    concern = _extract_section(text, "HIDDEN_CONCERN", default="")
    conditions_text = _extract_section(text, "CONDITIONS", default="")
    conditions = [
        line.lstrip("- ").strip()
        for line in conditions_text.splitlines()
        if line.strip() and line.strip() != "-"
    ]
    trigger = _extract_section(text, "RATING_CHANGE_TRIGGER", default="")
    authority_raw = _extract_section(text, "MY_AUTHORITY", default="").strip().upper()
    authority = None
    for auth_type in (
        "VETO",
        "ESCALATION",
        "INDEPENDENT",
        "CHALLENGE",
        "PATIENT_SAFETY",
    ):
        if auth_type in authority_raw:
            authority = auth_type
            break

    return ParsedDeepResult(
        perspective_id=perspective_id,
        rating=rating,
        findings=findings,
        strongest_objection=objection.strip(),
        hidden_concern=concern.strip(),
        conditions=conditions,
        rating_change_trigger=trigger.strip(),
        authority=authority,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_rating(raw: str) -> str | None:
    cleaned = raw.strip().lower()
    if cleaned in VALID_RATINGS:
        return cleaned
    return RATING_ALIASES.get(cleaned)


def _extract_section(text: str, tag: str, default: str = "") -> str:
    pattern = rf"\[{tag}\]\s*(.*?)\s*\[/{tag}\]"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1) if m else default
