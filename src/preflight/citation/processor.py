"""
Preflight citation processor — 3-mode streaming citation with accumulation.

FIRST PRINCIPLE: Every claim in a board-ready document MUST trace to a source.
Citations are not optional decoration — they are the evidence chain that makes
the assessment defensible in front of the EA board and the FG/DPO.

SECOND ORDER: If citation accumulation breaks across persona rounds, we lose
attribution. Solution: CitationMapping grows monotonically — persona 1 adds
citations [1-3], persona 2 adds [4-5] or reuses [1,2], final synthesis uses
the full mapping to produce numbered references.

INVERSION: What makes citations fail? Three failure modes: (1) citations in
authority persona outputs get stripped, making VETO appear ungrounded; (2)
citation numbers shift between rounds, breaking cross-references; (3) duplicate
citations inflate reference counts. The three-mode system fixes all three.

Pattern inspired by Onyx's DynamicCitationProcessor, adapted for persona-
attributed EA assessments with [§K:source-id] and [§P:persona-id] markers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class CitationMode(str, Enum):
    HYPERLINK = "hyperlink"
    KEEP_MARKERS = "keep_markers"
    REMOVE = "remove"


@dataclass
class SourceDoc:
    source_id: str
    title: str = ""
    url: str = ""
    source_type: str = ""
    excerpt: str = ""
    persona: str = ""


@dataclass
class CitationInfo:
    citation_number: int
    document_id: str
    source_type: str
    persona_id: str = ""
    url: str = ""
    title: str = ""
    excerpt: str = ""


class CitationMapping:
    """Accumulates citation mappings across persona rounds.

    Grows monotonically — new sources get new numbers. Reusing an existing
    source gets its original number. Persona attribution is tracked so the
    final document shows WHO cited WHAT.
    """

    def __init__(self):
        self._number_to_source: dict[int, SourceDoc] = {}
        self._source_to_number: dict[str, int] = {}
        self._next_number: int = 1

    def add_source(
        self,
        source_id: str,
        title: str = "",
        url: str = "",
        source_type: str = "",
        persona_id: str = "",
        excerpt: str = "",
    ) -> int:
        if source_id in self._source_to_number:
            num = self._source_to_number[source_id]
            existing = self._number_to_source[num]
            if persona_id and persona_id not in existing.persona:
                existing.persona += f", {persona_id}" if existing.persona else persona_id
            return num

        num = self._next_number
        self._next_number += 1
        self._source_to_number[source_id] = num
        self._number_to_source[num] = SourceDoc(
            source_id=source_id,
            title=title,
            url=url,
            source_type=source_type,
            persona=persona_id,
            excerpt=excerpt,
        )
        return num

    def get_number(self, source_id: str) -> int | None:
        return self._source_to_number.get(source_id)

    def get_source(self, number: int) -> SourceDoc | None:
        return self._number_to_source.get(number)

    @property
    def sources(self) -> dict[int, SourceDoc]:
        return dict(self._number_to_source)

    @property
    def count(self) -> int:
        return len(self._number_to_source)

    def merge(self, other: "CitationMapping") -> None:
        for source_id, num in other._source_to_number.items():
            if source_id not in self._source_to_number:
                source = other._number_to_source[num]
                self.add_source(
                    source_id=source.source_id,
                    title=source.title,
                    url=source.url,
                    source_type=source.source_type,
                    persona_id=source.persona,
                    excerpt=source.excerpt,
                )

    def to_reference_list(self) -> list[dict]:
        refs = []
        for num in sorted(self._number_to_source.keys()):
            source = self._number_to_source[num]
            refs.append(
                {
                    "number": num,
                    "source_id": source.source_id,
                    "title": source.title,
                    "url": source.url,
                    "source_type": source.source_type,
                    "persona": source.persona,
                    "excerpt": source.excerpt[:200] if source.excerpt else "",
                }
            )
        return refs


PERSONA_CITE_PATTERN = re.compile(r"\[§P:(\w[\w-]*)\]", re.IGNORECASE)
KNOWLEDGE_CITE_PATTERN = re.compile(r"\[§K:([\w.-]+)\]", re.IGNORECASE)
BRACKET_NUM_PATTERN = re.compile(r"\[(\d{1,3})\]")
UNICODE_BRACKET_PATTERN = re.compile(r"[【［]\s*(\d{1,3})\s*[】］]")


class CitationProcessor:
    """3-mode citation processor for persona assessment output.

    Modes:
      HYPERLINK: Replace [§K:source-id] with [[N]](url) for final documents
      KEEP_MARKERS: Preserve [§K:source-id] and [§P:persona] for intermediate
      REMOVE: Strip all citation markers for authority persona outputs
    """

    def __init__(self, mode: CitationMode = CitationMode.KEEP_MARKERS):
        self.mode = mode
        self.mapping = CitationMapping()
        self._recent_cited: set[str] = set()
        self._in_code_block = False

    def process(
        self,
        text: str,
        persona_id: str = "",
        citation_map: CitationMapping | None = None,
    ) -> tuple[str, list[CitationInfo]]:
        if citation_map:
            self.mapping.merge(citation_map)

        citations: list[CitationInfo] = []
        result = text

        if self.mode == CitationMode.REMOVE:
            result = PERSONA_CITE_PATTERN.sub("", result)
            result = KNOWLEDGE_CITE_PATTERN.sub("", result)
            result = BRACKET_NUM_PATTERN.sub("", result)
            result = UNICODE_BRACKET_PATTERN.sub("", result)
            return result, citations

        for match in KNOWLEDGE_CITE_PATTERN.finditer(text):
            source_id = match.group(1)
            dedup_key = f"K:{source_id}"
            if dedup_key in self._recent_cited:
                continue
            self._recent_cited.add(dedup_key)
            num = self.mapping.add_source(
                source_id=source_id,
                source_type="KNOWLEDGE",
                persona_id=persona_id,
            )
            citations.append(
                CitationInfo(
                    citation_number=num,
                    document_id=source_id,
                    source_type="KNOWLEDGE",
                    persona_id=persona_id,
                )
            )

        if self.mode == CitationMode.HYPERLINK:
            for match in KNOWLEDGE_CITE_PATTERN.finditer(text):
                source_id = match.group(1)
                num = self.mapping.get_number(source_id)
                if num:
                    source = self.mapping.get_source(num)
                    url = source.url if source else ""
                    if url:
                        replacement = f"[[{num}]]({url})"
                    else:
                        replacement = f"[{num}]"
                    result = result.replace(match.group(0), replacement, 1)

        for match in PERSONA_CITE_PATTERN.finditer(text):
            pid = match.group(1)
            dedup_key = f"P:{pid}"
            if dedup_key in self._recent_cited:
                continue
            self._recent_cited.add(dedup_key)
            num = self.mapping.add_source(
                source_id=f"persona:{pid}",
                source_type="PERSONA",
                persona_id=pid,
            )
            citations.append(
                CitationInfo(
                    citation_number=num,
                    document_id=f"persona:{pid}",
                    source_type="PERSONA",
                    persona_id=pid,
                )
            )

        if self.mode == CitationMode.HYPERLINK:
            for match in PERSONA_CITE_PATTERN.finditer(text):
                pid = match.group(1)
                num = self.mapping.get_number(f"persona:{pid}")
                if num:
                    result = result.replace(match.group(0), f"[{num}]", 1)

        return result, citations

    def reset_recent(self) -> None:
        self._recent_cited.clear()

    def format_references(self) -> str:
        refs = self.mapping.to_reference_list()
        if not refs:
            return ""
        lines = ["## Referenties\n"]
        for ref in refs:
            persona_str = f" ({ref['persona']})" if ref["persona"] else ""
            if ref["title"]:
                label = ref["title"]
            elif ref["source_id"].startswith("persona:"):
                label = ref["source_id"].replace("persona:", "")
            else:
                label = ref["source_id"]
            source_type = f" [{ref['source_type']}]" if ref["source_type"] else ""
            lines.append(f"[{ref['number']}] {label}{source_type}{persona_str}")
        return "\n".join(lines)
