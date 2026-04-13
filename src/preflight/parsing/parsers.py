"""
Preflight document parsing pipeline — chain of parsers with quality validation.

Fallback chain (Workhorse mode):
  MarkItDown → PyMuPDF → raw text extraction → failure flag

Smart mode (vendor contracts, complex specs):
  LlamaParse → MarkItDown → PyMuPDF → failure flag

Every parsed document gets:
  - Parse quality validation (page count, size ratio, table detection)
  - Content type detection (regulatory, vendor, policy, tabular)
  - Language detection (NL/EN/mixed)
  - Section structure extraction
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, Sequence


class ParseMode(str, Enum):
    WORKHORSE = "workhorse"
    SMART = "smart"


@dataclass
class ParsedDocument:
    source_file: str
    content: str
    title: str = ""
    language: str = "nl"
    content_type: str = "generic"
    page_count: int = 0
    has_tables: bool = False
    sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def quality_ok(self) -> bool:
        return len(self.errors) == 0 and "could not be parsed" not in self.content


class DocumentParser(Protocol):
    async def parse(self, file_path: str | Path) -> ParsedDocument: ...

    def supported_extensions(self) -> list[str]: ...


class MarkItDownParser:
    """Office document parser using MarkItDown (DOCX, PPTX, XLSX).

    MarkItDown converts Office documents to Markdown with structure preservation.
    Self-hosted, no data residency concerns.
    """

    def supported_extensions(self) -> list[str]:
        return [".docx", ".pptx", ".xlsx", ".xls", ".doc", ".rtf"]

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)
        ext = path.suffix.lower()

        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(str(path))
            content = result.text_content

            if not content or len(content.strip()) < 10:
                return ParsedDocument(
                    source_file=str(path),
                    content="",
                    errors=["MarkItDown produced empty or minimal output"],
                )

            title = result.title or path.stem
            has_tables = "|" in content and "---" in content

            return ParsedDocument(
                source_file=str(path),
                content=content,
                title=title,
                language=_detect_language(content),
                content_type=_detect_content_type(content, ext),
                has_tables=has_tables,
                sections=_extract_sections(content),
                metadata={"parser": "markitdown", "extension": ext},
            )
        except ImportError:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=["markitdown not installed: pip install markitdown"],
            )
        except Exception as e:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=[f"MarkItDown failed: {e}"],
            )


class PyMuPDFParser:
    """PDF parser using PyMuPDF (fitz) with table + chapter extraction.

    Extracts:
    - Text per page with page number metadata
    - Tables as Markdown tables (preserving control matrices for NEN 7510-2)
    - Chapter/section structure from document outlines and heading detection
    - Verse tags extracted from filename or metadata (e.g. NEN 7510-1_2024 → versie: 2024)
    """

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)

        try:
            import fitz

            doc = fitz.open(str(path))
            try:
                page_count = len(doc)
                versie = _extract_versie_from_pdf(doc) or _extract_versie(path.name)

                outline = doc.get_toc() or []
                toc_entries: list[dict] = []
                for entry in outline:
                    if len(entry) >= 3:
                        lvl, title, pg = entry[:3]
                        toc_entries.append({"level": lvl, "title": title, "page": pg})

                has_tables = False
                page_texts: dict[int, str] = {}
                page_tables: dict[int, list[str]] = {}

                for page_idx, page in enumerate(doc):
                    page_num = page_idx + 1
                    text = page.get_text("text")
                    tables_md: list[str] = []

                    try:
                        for table in page.find_tables():
                            try:
                                md = table.to_markdown()
                                if md and md.strip():
                                    tables_md.append(md)
                                    has_tables = True
                            except Exception:
                                pass
                    except Exception:
                        pass

                    if text.strip():
                        page_texts[page_num] = text.strip()
                    if tables_md:
                        page_tables[page_num] = tables_md

                doc.close()
            except Exception:
                doc.close()
                raise

            if not page_texts:
                return ParsedDocument(
                    source_file=str(path),
                    content="",
                    page_count=page_count,
                    errors=["PDF contains no extractable text (possibly scanned)"],
                )

            if toc_entries:
                content = _build_page_sections_with_toc(page_texts, page_tables, toc_entries)
            else:
                content = _build_page_sections(page_texts, page_tables)

            title = path.stem
            if toc_entries:
                for entry in toc_entries:
                    if entry["level"] == 1:
                        title = entry["title"]
                        break
            else:
                first_text = next(iter(page_texts.values()), "")
                title_match = re.search(r"^(#{1,3}\s+)?(.+?)\n", first_text)
                if title_match:
                    title = title_match.group(2).strip()

            sections = [e["title"] for e in toc_entries if e["level"] <= 3]

            return ParsedDocument(
                source_file=str(path),
                content=content,
                title=title,
                language=_detect_language(next(iter(page_texts.values()), "")),
                content_type=_detect_content_type(next(iter(page_texts.values()), ""), ".pdf"),
                page_count=page_count,
                has_tables=has_tables,
                sections=sections,
                metadata={
                    "parser": "pymupdf",
                    "page_count": page_count,
                    "versie": versie,
                    "toc": toc_entries,
                    "has_outline": bool(toc_entries),
                },
            )
        except ImportError:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=["PyMuPDF not installed: pip install PyMuPDF"],
            )
        except Exception as e:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=[f"PyMuPDF failed: {e}"],
            )


class TextParser:
    """Plain text and Markdown parser — no conversion needed."""

    def supported_extensions(self) -> list[str]:
        return [".md", ".txt", ".markdown", ".rst"]

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="latin-1")
            except Exception as e:
                return ParsedDocument(
                    source_file=str(path),
                    content="",
                    errors=[f"Could not read file: {e}"],
                )

        if not content.strip():
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=["File is empty"],
            )

        title = path.stem
        title_match = re.search(r"^#\s+(.+)", content)
        if title_match:
            title = title_match.group(1).strip()

        return ParsedDocument(
            source_file=str(path),
            content=content,
            title=title,
            language=_detect_language(content),
            content_type=_detect_content_type(content, path.suffix),
            sections=_extract_sections(content),
            metadata={"parser": "text"},
        )


class LlamaParseParser:
    """Smart parser using LlamaParse for complex documents.

    AI-powered understanding for vendor contracts, regulatory mapping,
    cross-referenced tables. Requires API key and data residency considerations.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def supported_extensions(self) -> list[str]:
        return [".pdf", ".docx", ".pptx", ".xlsx"]

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)

        try:
            from llama_parse import LlamaParse

            api_key = self.api_key or os.environ.get("LLAMA_CLOUD_API_KEY", "")
            if not api_key:
                return ParsedDocument(
                    source_file=str(path),
                    content="",
                    errors=["LlamaParse API key not configured"],
                )

            parser = LlamaParse(api_key=api_key, result_type="markdown")
            result = await parser.aload_data(str(path))

            content = "\n\n".join(doc.text for doc in result)

            if not content.strip():
                return ParsedDocument(
                    source_file=str(path),
                    content="",
                    errors=["LlamaParse produced empty output"],
                )

            return ParsedDocument(
                source_file=str(path),
                content=content,
                title=path.stem,
                language=_detect_language(content),
                content_type=_detect_content_type(content, path.suffix),
                has_tables="|" in content,
                sections=_extract_sections(content),
                metadata={"parser": "llamaparse"},
            )
        except ImportError:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=["llama-parse not installed: pip install llama-parse"],
            )
        except Exception as e:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=[f"LlamaParse failed: {e}"],
            )


class UnstructuredParser:
    """Parser using Unstructured.io for complex document layouts.

    Handles HTML, XML, and other structured formats that MarkItDown/PyMuPDF
    don't support well. Self-hosted via Docker; no data residency concerns.
    """

    def supported_extensions(self) -> list[str]:
        return [".html", ".htm", ".xml", ".epub", ".odt", ".ods", ".odp"]

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)

        try:
            from unstructured.partition.auto import partition

            elements = partition(filename=str(path))
            content = "\n\n".join(str(el) for el in elements)

            if not content.strip():
                return ParsedDocument(
                    source_file=str(path),
                    content="",
                    errors=["Unstructured produced empty output"],
                )

            has_tables = any("Table" in type(el).__name__ for el in elements)

            return ParsedDocument(
                source_file=str(path),
                content=content,
                title=path.stem,
                language=_detect_language(content),
                content_type=_detect_content_type(content, path.suffix),
                has_tables=has_tables,
                sections=_extract_sections(content),
                metadata={"parser": "unstructured", "element_count": len(elements)},
            )
        except ImportError:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=["unstructured not installed: pip install unstructured"],
            )
        except Exception as e:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=[f"Unstructured failed: {e}"],
            )


class ParsingPipeline:
    """Chain-of-responsibility document parser.

    Tries parsers in order based on the selected mode.
    No document silently fails.
    """

    def __init__(
        self,
        mode: ParseMode = ParseMode.WORKHORSE,
        llamaparse_key: str | None = None,
    ):
        self.mode = mode

        self._workhorse: list[DocumentParser] = [
            MarkItDownParser(),
            PyMuPDFParser(),
            UnstructuredParser(),
            TextParser(),
        ]

        self._smart: list[DocumentParser] = [
            LlamaParseParser(llamaparse_key),
        ] + self._workhorse

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)
        ext = path.suffix.lower()

        chain = self._smart if self.mode == ParseMode.SMART else self._workhorse

        applicable = [
            p for p in chain if ext in p.supported_extensions() or not p.supported_extensions()
        ]

        if not applicable:
            return ParsedDocument(
                source_file=str(path),
                content="",
                errors=[f"Unsupported file type: {ext}"],
            )

        last_result = None
        for parser in applicable:
            result = await parser.parse(path)

            if result.quality_ok:
                self._validate_quality(path, result)
                return result

            last_result = result

        if last_result and last_result.content:
            self._validate_quality(path, last_result)
            return last_result

        return ParsedDocument(
            source_file=str(path),
            content=f"⚠ This document could not be parsed: {path.name}. "
            f"Please provide the content in another format.",
            errors=["All parsers failed"],
        )

    def _validate_quality(self, path: Path, result: ParsedDocument) -> None:
        """Check parse quality and add warnings if needed."""
        file_size = path.stat().st_size if path.exists() else 0

        if result.page_count and file_size:
            text_per_page = len(result.content) / max(1, result.page_count)
            if text_per_page < 100:
                result.warnings.append(
                    f"Suspiciously little text per page ({text_per_page:.0f} chars). "
                    f"Document may be scanned or image-based."
                )

        if len(result.content) < file_size * 0.05 and file_size > 1000:
            result.warnings.append("Parsed output is suspiciously small relative to file size")

        if not result.has_tables and self._likely_has_tables(path):
            result.warnings.append("Original file may contain tables that were not extracted")

        if self._has_numbering_gaps(result.content):
            result.warnings.append("Section numbering gap detected — content may be missing")

    def _likely_has_tables(self, path: Path) -> bool:
        ext = path.suffix.lower()
        return ext in (".xlsx", ".xls", ".csv") or (ext == ".pdf" and path.stat().st_size > 50000)

    def _has_numbering_gaps(self, text: str) -> bool:
        headers = re.findall(r"^#{1,4}\s+(\d+(?:\.\d+)*)", text, re.MULTILINE)
        if len(headers) < 3:
            return False
        nums = []
        for h in headers:
            try:
                nums.append(float(h))
            except ValueError:
                pass
        if len(nums) < 3:
            return False
        for i in range(1, len(nums)):
            if nums[i] - nums[i - 1] > 2:
                return True
        return False


def _detect_language(text: str) -> str:
    """Simple language detection based on common Dutch/English markers."""
    if not text:
        return "nl"

    dutch_markers = [
        "de ",
        "het ",
        "een ",
        "van ",
        "en ",
        "in ",
        "dat ",
        "voor ",
        "zorg",
        "patiënt",
        "ziekenhuis",
        "beleid",
        "informatie",
        "verwerking",
        "persoonsgegevens",
        "beveiliging",
    ]
    english_markers = [
        "the ",
        "is ",
        "are ",
        "and ",
        "for ",
        "with ",
        "that ",
        "hospital",
        "patient",
        "security",
        "compliance",
        "privacy",
    ]

    sample = text[:3000].lower()
    dutch_count = sum(1 for m in dutch_markers if m in sample)
    english_count = sum(1 for m in english_markers if m in sample)

    if dutch_count > english_count + 2:
        return "nl"
    elif english_count > dutch_count + 2:
        return "en"
    else:
        return "mixed"


def _detect_content_type(text: str, extension: str) -> str:
    """Detect the likely content type from document content."""
    if not text:
        return "generic"

    sample = text[:5000].lower()

    regulatory_markers = [
        "nen 7510",
        "nen 7512",
        "nen 7513",
        "avg",
        "gdpr",
        "aivg",
        "nis2",
        "mdr",
        "ivdr",
        "artikel",
        "article",
        "richtlijn",
        "directive",
        "verordening",
        "regulation",
        "iso 27001",
        "eugen-ai-verordening",
        "eu ai act",
    ]
    vendor_markers = [
        "vendor",
        "supplier",
        "contract",
        "sla",
        "service level",
        "leverancier",
        "overeenkomst",
        "proposal",
        "quotation",
        "datasheet",
        " specification",
    ]
    policy_markers = [
        "beleid",
        "policy",
        "procedure",
        "werk instructie",
        "work instruction",
        "standard operating",
        "protocol",
        "richtlijn",
        "guideline",
    ]

    reg_count = sum(1 for m in regulatory_markers if m in sample)
    vendor_count = sum(1 for m in vendor_markers if m in sample)
    policy_count = sum(1 for m in policy_markers if m in sample)

    if extension in (".xlsx", ".xls", ".csv"):
        return "tabular"

    scores = {
        "regulatory": reg_count,
        "vendor": vendor_count,
        "policy": policy_count,
    }

    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best

    return "generic"


def _extract_sections(text: str) -> list[str]:
    """Extract section headers from Markdown text."""
    headers = re.findall(r"^#{1,4}\s+(.+)", text, re.MULTILINE)
    return [h.strip() for h in headers]


def _detect_table_structure(text: str) -> bool:
    """Detect if a page contains table-like structures."""
    lines = text.split("\n")
    pipe_lines = sum(1 for l in lines if l.strip().startswith("|"))
    return pipe_lines >= 2


def _extract_versie(filename: str) -> str:
    """Extract version tag from filename.

    Examples:
      "NEN 7510-1_2024 nl.pdf" → "2024"
      "NEN 7510-2_2024+A1_2026 nl.pdf" → "2024+A1:2026"
      "NEN 7510-2_2024+A2_2026 nl.pdf" → "2024+A2:2026"
      "NTA 7516_2019 nl.pdf" → "2019"
      "Bedrijfsarchitectuur op basis van NAR - Hans Tonissen.pdf" → "2013"
    """
    match = re.search(r"_(\d{4})(?:\+A(\d+))?(?:_(\d{4}))?(?=\s)", filename)
    if match:
        year = match.group(1)
        amendment = match.group(2)
        ext_year = match.group(3)
        if amendment and ext_year:
            return f"{year}+A{amendment}:{ext_year}"
        if amendment:
            return f"{year}+A{amendment}"
        return year
    book_match = re.search(r"(?:Hans\s*Tonissen|Bedrijfsarchitectuur)", filename)
    if book_match:
        return "2013"
    return "unknown"


def _extract_versie_from_pdf(doc) -> str | None:
    """Extract version from PDF colophon / first pages.

    Scans the first 10 pages for "Xe druk" (dutch edition) or
    "Xth edition" patterns and extracts the year.
    Returns the MOST RECENT (last) edition found — a book may list
    "Eerste druk 2009 / Tweede druk 2013" in its colophon.
    Returns None if nothing found — caller falls back to filename.
    """
    colophon_pattern = re.compile(
        r"(?:eerste|tweede|derde|vierde)\s+druk.*?(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+(\d{4})",
        re.IGNORECASE,
    )
    edition_pattern = re.compile(
        r"(?:first|second|third|fourth)\s+edition.*?(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
        re.IGNORECASE,
    )

    last_year: str | None = None
    for page in doc[:10]:
        text = page.get_text()
        for pat in (colophon_pattern, edition_pattern):
            for m in pat.finditer(text):
                last_year = m.group(1)
    return last_year


def _find_chapter_for_page(toc: list[dict], page_num: int) -> str:
    """Find the top-level chapter title for a given page number."""
    current = ""
    for entry in toc:
        if entry["level"] == 1 and entry["page"] <= page_num:
            current = entry["title"]
        elif entry["page"] > page_num:
            break
    return current


def _find_section_for_page(toc: list[dict], page_num: int) -> str:
    """Find the most specific section title for a given page number."""
    current = ""
    for entry in toc:
        if entry["page"] <= page_num and entry["level"] <= 3:
            current = entry["title"]
        elif entry["page"] > page_num:
            break
    return current


def _build_page_sections_with_toc(
    page_texts: dict[int, str],
    page_tables: dict[int, list[str]],
    toc_entries: list[dict],
) -> str:
    """Page-based sections enriched with TOC chapter/section metadata.

    Uses ## Page N headers (proven to work better for chunking) but appends
    the TOC-derived chapter and section titles so chunks carry rich metadata.
    """
    parts: list[str] = []
    for pg in sorted(page_texts.keys()):
        chapter = _find_chapter_for_page(toc_entries, pg)
        section = _find_section_for_page(toc_entries, pg)
        header = f"## Page {pg}"
        if chapter:
            header += f" — {chapter}"
        if section and section != chapter:
            header += f" › {section}"
        section_parts = [page_texts[pg]]
        section_parts.extend(page_tables.get(pg, []))
        parts.append(f"{header}\n\n" + "\n\n".join(section_parts))
    return "\n\n---\n\n".join(parts)


def _build_toc_sections(
    page_texts: dict[int, str],
    page_tables: dict[int, list[str]],
    toc_entries: list[dict],
) -> str:
    """Build Markdown content organized by TOC sections, not pages.

    Uses the document's own outline to create proper ## and ### headers
    that match the actual document structure. This enables parent/child
    chunking to create meaningful section-based chunks instead of page-based ones.
    """
    level_headers = {1: "##", 2: "###", 3: "####"}
    max_page = max(page_texts.keys()) if page_texts else 1

    section_ranges: list[tuple[dict, int]] = []
    for i, entry in enumerate(toc_entries):
        start_page = entry["page"]
        end_page = max_page + 1
        for j in range(i + 1, len(toc_entries)):
            if toc_entries[j]["level"] <= entry["level"]:
                end_page = toc_entries[j]["page"]
                break
        section_ranges.append((entry, end_page))

    toc_by_page: dict[int, list[dict]] = {}
    for entry, end_page in section_ranges:
        for pg in range(entry["page"], min(end_page, max_page + 1)):
            toc_by_page.setdefault(pg, []).append(entry)

    seen_pages: set[int] = set()
    parts: list[str] = []
    emitted_sections: set[str] = set()

    for entry, end_page in section_ranges:
        title = entry["title"].strip()
        section_key = f"{entry['level']}:{title}"
        if section_key in emitted_sections:
            continue
        emitted_sections.add(section_key)

        header_prefix = level_headers.get(entry["level"], "###")
        section_content_parts: list[str] = []

        for pg in range(entry["page"], min(end_page, max_page + 1)):
            if pg in page_texts and pg not in seen_pages:
                seen_pages.add(pg)
                section_content_parts.append(page_texts[pg])
            if pg in page_tables:
                for tbl in page_tables[pg]:
                    section_content_parts.append(tbl)

        if not section_content_parts:
            continue

        header = f"{header_prefix} {title}"
        section_text = "\n\n".join(section_content_parts)
        parts.append(f"{header}\n\n{section_text}")

    for pg in sorted(page_texts.keys()):
        if pg not in seen_pages:
            seen_pages.add(pg)
            section_parts = [page_texts[pg]]
            section_parts.extend(page_tables.get(pg, []))
            parts.append(f"## Page {pg}\n\n" + "\n\n".join(section_parts))

    return "\n\n---\n\n".join(parts)


def _build_page_sections(
    page_texts: dict[int, str],
    page_tables: dict[int, list[str]],
) -> str:
    """Fallback: build page-based sections when no TOC is available."""
    parts: list[str] = []
    for pg in sorted(page_texts.keys()):
        section_parts = [page_texts[pg]]
        section_parts.extend(page_tables.get(pg, []))
        parts.append(f"## Page {pg}\n\n" + "\n\n".join(section_parts))
    return "\n\n---\n\n".join(parts)
