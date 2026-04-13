"""
Preflight chunk enrichment — dual enrichment for keyword and semantic search.

FIRST PRINCIPLE: The same chunk needs different enrichment depending on HOW it will
be searched. Keyword search needs NEN numbers, regulatory references, and exact terms.
Semantic search needs natural language descriptions and domain context.

SECOND ORDER: If we enrich wrong, we embed noise. Fallback: always include the raw
chunk text unchanged. Enrichment is additive prefix/suffix — never replacement.

INVERSION: What makes enrichment fail? Over-enrichment drowns signal in noise.
Solution: budget metadata to 25% of chunk length (Onyx's proven ratio), and cleanup
enrichment on retrieval so users never see the metadata gunk.

Dual enrichment pattern inspired by Onyx's generate_enriched_content_for_chunk_text/
generate_enriched_content_for_chunk_embedding, adapted for Dutch hospital context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_METADATA_PERCENTAGE = 0.25
SECTION_SEPARATOR = "\n---\n"

ZIRA_PRINCIPLES = {
    "principe-1": "Gebruiker centraal — User needs drive architecture",
    "principe-2": "Sturen op waarden — Architecture governed by public values",
    "principe-3": "Samenwerken — Collaborate across organizational boundaries",
    "principe-4": "Standaardiseren — Use standards before building custom",
    "principe-5": "Beheerbaar — Maintainability as first-class concern",
    "principe-6": "Veilig — Security and privacy by design (NEN 7510/7513/AVG)",
    "principe-7": "Betrouwbaar — Reliability and continuity (NEN 7510 BIV)",
    "principe-8": "Flexibel — Architecture supports change",
    "principe-9": "Verantwoord — Accountability and traceability",
    "principe-10": "Transparant — Architecture decisions are visible",
    "principe-11": "Efficiënt — Optimize resource usage",
    "principe-12": "Inkoopvastheid — Procurement discipline in vendor selection",
}

REGULATORY_TERMS = {
    "nen7510": "NEN 7510 — Information security in healthcare",
    "nen7512": "NEN 7512 — Application of NEN 7510",
    "nen7513": "NEN 7513 — Audit logging in healthcare",
    "nen7516": "NEN 7516 — Password management in healthcare",
    "nen7517": "NEN 7517 — Cryptography in healthcare",
    "avg": "AVG (UAVG) — Algemene Verordening Gegevensbescherming",
    "gdpr": "GDPR — General Data Protection Regulation",
    "mdr": "MDR — Medical Device Regulation (EU 2017/745)",
    "ivdr": "IVDR — In Vitro Diagnostic Regulation (EU 2022/986)",
    "nis2": "NIS2 — Network and Information Security Directive",
    "wegiz": "Wegiz — Wet gewellijke elektronische gegevensuitwisseling in de zorg",
    "aivg": "AiVG 2022 — Algemene wet Inrichting Zorg",
    "zira": "ZiRA — Ziekenhuis Referentie Architectuur",
}


@dataclass
class EnrichedChunk:
    original: str
    doc_summary: str = ""
    chunk_context: str = ""
    zira_principles: list[str] = field(default_factory=list)
    regulatory_references: list[str] = field(default_factory=list)
    persona_tags: list[str] = field(default_factory=list)
    source_type: str = ""
    language: str = "nl"
    title_prefix: str = ""

    @property
    def keyword_enriched(self) -> str:
        content = self._apply_metadata_budget(
            self._build_keyword_suffix(), mode="keyword"
        )
        parts = []
        if self.title_prefix:
            parts.append(self.title_prefix)
        if self.doc_summary:
            parts.append(f"SAMENVATTING: {self.doc_summary}")
        if self.chunk_context:
            parts.append(f"CONTEXT: {self.chunk_context}")
        parts.append(self.original)
        parts.append(content)
        return SECTION_SEPARATOR.join(p for p in parts if p)

    @property
    def semantic_enriched(self) -> str:
        content = self._apply_metadata_budget(
            self._build_semantic_suffix(), mode="semantic"
        )
        parts = []
        if self.title_prefix:
            parts.append(self.title_prefix)
        if self.doc_summary:
            parts.append(f"Summary: {self.doc_summary}")
        if self.chunk_context:
            parts.append(f"Context: {self.chunk_context}")
        parts.append(self.original)
        parts.append(content)
        return SECTION_SEPARATOR.join(p for p in parts if p)

    def cleanup_for_display(self, text: str) -> str:
        stripped = text
        for prefix in ("SAMENVATTING: ", "Summary: ", "CONTEXT: ", "Context: "):
            if stripped.startswith(prefix):
                idx = stripped.find(SECTION_SEPARATOR)
                if idx >= 0:
                    stripped = stripped[idx + len(SECTION_SEPARATOR) :]
                else:
                    stripped = stripped[len(prefix) :]
                break
        for marker in ("METADATA_KEYWORD: ", "METADATA_SEMANTIC: "):
            idx = stripped.rfind(marker)
            if idx >= 0:
                stripped = stripped[:idx]
        return stripped.strip()

    def _build_keyword_suffix(self) -> str:
        lines = []
        if self.zira_principles:
            lines.append("ZIRA: " + " | ".join(self.zira_principles))
        if self.regulatory_references:
            lines.append("REGS: " + " | ".join(self.regulatory_references))
        if self.persona_tags:
            lines.append("DOMAIN: " + " | ".join(self.persona_tags))
        if self.source_type:
            lines.append("TYPE: " + self.source_type)
        return "\n".join(lines)

    def _build_semantic_suffix(self) -> str:
        lines = []
        if self.zira_principles:
            lines.extend(f"ZiRA principle: {p}" for p in self.zira_principles)
        if self.regulatory_references:
            lines.extend(f"Regulation: {r}" for r in self.regulatory_references)
        if self.persona_tags:
            lines.append(f"Relevant domains: {', '.join(self.persona_tags)}")
        if self.source_type:
            lines.append(f"Document type: {self.source_type}")
        return "\n".join(lines)

    def _apply_metadata_budget(self, metadata_text: str, mode: str = "keyword") -> str:
        if not metadata_text:
            return ""
        max_meta = int(len(self.original) * MAX_METADATA_PERCENTAGE)
        if len(metadata_text) <= max_meta:
            return metadata_text
        truncated = metadata_text[:max_meta]
        last_newline = truncated.rfind("\n")
        if last_newline > max_meta * 0.5:
            truncated = truncated[:last_newline]
        prefix = "METADATA_KEYWORD: " if mode == "keyword" else "METADATA_SEMANTIC: "
        return prefix + truncated


def detect_regulatory_references(text: str) -> list[str]:
    detected = []
    text_lower = text.lower()
    for term, description in REGULATORY_TERMS.items():
        patterns = [term, term.replace("nen", "nen "), term.replace("7510", "7510:")]
        for pattern in patterns:
            if pattern in text_lower:
                detected.append(description)
                break
    for match in re.findall(
        r"NEN\s*(\d{4})(?:[-:](\d+(?:\.\d+)*))?", text, re.IGNORECASE
    ):
        nen_num = match[0]
        section = match[1] if match[1] else ""
        ref = f"NEN {nen_num}"
        if section:
            ref += f" §{section}"
        if ref not in " ".join(detected):
            for term_key, term_desc in REGULATORY_TERMS.items():
                if nen_num in term_key:
                    detected.append(term_desc)
                    break
    return detected


def detect_zira_principles(text: str) -> list[str]:
    text_lower = text.lower()
    detected = []
    for pid, desc in ZIRA_PRINCIPLES.items():
        if pid in text_lower or any(
            kw in text_lower for kw in desc.lower().split()[:3]
        ):
            detected.append(f"{pid}: {desc}")
    return detected


def enrich_chunk(
    content: str,
    title: str = "",
    doc_summary: str = "",
    chunk_context: str = "",
    source_type: str = "",
    persona_tags: list[str] | None = None,
    language: str = "nl",
) -> EnrichedChunk:
    zira = detect_zira_principles(content)
    regs = detect_regulatory_references(content)
    return EnrichedChunk(
        original=content,
        doc_summary=doc_summary,
        chunk_context=chunk_context,
        zira_principles=zira,
        regulatory_references=regs,
        persona_tags=persona_tags or [],
        source_type=source_type,
        language=language,
        title_prefix=f"TITLE: {title}" if title else "",
    )
