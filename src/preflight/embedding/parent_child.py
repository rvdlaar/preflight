"""
Preflight parent/child chunking — LangChain ParentDocumentRetriever pattern.

Every chunk is a "child" (small, for precise retrieval) that points to a
"parent" (large, for context expansion). When a child matches, the retriever
fetches the full parent section — so the AI sees the whole maatregel, not just
a snippet.

Metadata is koning: every chunk carries chapter_num, chapter_title, section,
versie, and parent_id from day one.

Design:
  Parent = a document section (## or ### header block), typically 1500-3000 tokens
  Child  = a paragraph or paragraph group within that section, 300-512 tokens
  Tables = always kept intact as a single child that points to its section parent
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Sequence

from preflight.embedding.chunking import Chunk, ChunkingConfig


@dataclass
class ParentSection:
    id: str
    text: str
    chapter_num: int
    chapter_title: str
    section_title: str
    start_char: int
    end_char: int
    versie: str = ""
    source_id: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text.split()))


@dataclass
class ChildChunk(Chunk):
    parent_id: str = ""
    chapter_num: int = 0
    chapter_title: str = ""
    versie: str = ""


def parent_child_chunk(
    text: str,
    content_type: str = "generic",
    metadata: dict | None = None,
    child_size: int = 512,
    child_overlap: int = 77,
    parent_min_tokens: int = 100,
    table_intact: bool = True,
) -> tuple[list[ParentSection], list[ChildChunk]]:
    """Split text into parent sections and child chunks.

    Returns (parents, children) where every child has a parent_id reference.
    Parent sections are determined by ## / ### headers in the text.
    Tables are kept as single child chunks when table_intact=True.

    This is the core of the ParentDocumentRetriever pattern.
    """
    meta = metadata or {}
    versie = meta.get("versie", "unknown")
    source_id = meta.get("source_id", "")

    sections = _split_into_sections(text)
    parents: list[ParentSection] = []
    children: list[ChildChunk] = []
    chapter_num = 0
    current_chapter = ""

    for i, (header, section_text, start, end) in enumerate(sections):
        if not section_text.strip():
            continue

        header_level = 0
        header_match = re.match(r"^(#{1,3})\s+", header) if header else None
        if header_match:
            header_level = len(header_match.group(1))
        is_chapter = header_level == 1 or (
            header_level == 2 and re.match(r"^##\s+\d+[\.\s]", header)
        )
        if is_chapter:
            chapter_num += 1
            current_chapter = header.lstrip("# ").strip()
        section_title = header.lstrip("# ").strip() if header else ""
        if is_chapter:
            current_chapter = section_title

        parent_id = str(uuid.uuid4())[:8]
        parent = ParentSection(
            id=parent_id,
            text=section_text.strip(),
            chapter_num=chapter_num,
            chapter_title=current_chapter,
            section_title=section_title,
            start_char=start,
            end_char=end,
            versie=versie,
            source_id=source_id,
            metadata={**meta, "chapter_num": chapter_num, "chapter_title": current_chapter},
        )
        parents.append(parent)

        table_blocks, non_table_text = (
            _separate_tables(section_text) if table_intact else ([], section_text)
        )

        for table_md in table_blocks:
            if len(table_md.strip()) < 20:
                continue
            children.append(
                ChildChunk(
                    text=table_md.strip(),
                    index=len(children),
                    start_char=section_text.find(table_md) + start
                    if table_md in section_text
                    else start,
                    end_char=start + len(section_text),
                    content_type=content_type,
                    parent_id=parent_id,
                    chapter_num=chapter_num,
                    chapter_title=current_chapter,
                    versie=versie,
                    metadata={
                        **meta,
                        "parent_id": parent_id,
                        "chapter_num": chapter_num,
                        "chapter_title": current_chapter,
                        "section": section_title,
                        "is_table": True,
                    },
                )
            )

        if non_table_text.strip():
            child_chunks = _split_to_children(
                non_table_text,
                content_type,
                child_size,
                child_overlap,
                meta,
            )
            for child in child_chunks:
                children.append(
                    ChildChunk(
                        text=child.text,
                        index=len(children),
                        start_char=child.start_char + start,
                        end_char=child.end_char + start,
                        content_type=content_type,
                        parent_id=parent_id,
                        chapter_num=chapter_num,
                        chapter_title=current_chapter,
                        versie=versie,
                        metadata={
                            **child.metadata,
                            "parent_id": parent_id,
                            "chapter_num": chapter_num,
                            "chapter_title": current_chapter,
                            "section": section_title,
                        },
                    )
                )

    if not parents and len(text.strip()) >= 50:
        parent_id = str(uuid.uuid4())[:8]
        parent = ParentSection(
            id=parent_id,
            text=text.strip(),
            chapter_num=0,
            chapter_title="",
            section_title="",
            start_char=0,
            end_char=len(text),
            versie=versie,
            source_id=source_id,
            metadata=meta,
        )
        parents.append(parent)

        cfg = ChunkingConfig(chunk_size=child_size, chunk_overlap=child_overlap)
        child_chunks = _simple_split(text, cfg)
        for child in child_chunks:
            children.append(
                ChildChunk(
                    text=child.text,
                    index=len(children),
                    start_char=child.start_char,
                    end_char=child.end_char,
                    content_type=content_type,
                    parent_id=parent_id,
                    versie=versie,
                    metadata={**meta, "parent_id": parent_id},
                )
            )

    return parents, children


def _split_into_sections(text: str) -> list[tuple[str, str, int, int]]:
    """Split text at ## / ### header boundaries.

    Returns list of (header, section_text, start_char, end_char).
    """
    header_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(text))

    if not matches:
        return [("", text, 0, len(text))]

    sections: list[tuple[str, str, int, int]] = []

    if matches[0].start() > 0:
        pre = text[: matches[0].start()]
        if pre.strip():
            sections.append(("", pre, 0, matches[0].start()))

    for i, match in enumerate(matches):
        header = match.group(0)
        level = len(match.group(1))
        title = match.group(2).strip()
        section_start = match.start()

        section_end = len(text)
        for j in range(i + 1, len(matches)):
            if len(matches[j].group(1)) <= level:
                section_end = matches[j].start()
                break

        section_text = text[section_start:section_end]
        sections.append((header, section_text, section_start, section_end))

    return sections


_TABLE_PATTERN = re.compile(
    r"(\|[^\n]+\|\n(?:\|[-: ]+[-| :]+\|\n)?(?:\|[^\n]+\|\n)+)",
    re.MULTILINE,
)


def _separate_tables(text: str) -> tuple[list[str], str]:
    """Separate Markdown tables from surrounding text.

    Returns (table_blocks, remaining_text).
    Tables are kept as complete blocks for intact chunking.
    """
    tables = [m.group(1).strip() for m in _TABLE_PATTERN.finditer(text)]
    remaining = _TABLE_PATTERN.sub("", text)
    return tables, remaining


def _split_to_children(
    text: str,
    content_type: str,
    chunk_size: int,
    chunk_overlap: int,
    metadata: dict,
) -> list[Chunk]:
    """Split a section's non-table text into child chunks."""
    cfg = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    paragraphs = re.split(r"\n\n+", text)
    chunks: list[Chunk] = []
    current = ""
    position = 0

    for para in paragraphs:
        if not para.strip():
            continue

        if len((current + "\n\n" + para).split()) > chunk_size and current.strip():
            chunks.append(
                Chunk(
                    text=current.strip(),
                    index=len(chunks),
                    start_char=position,
                    end_char=position + len(current),
                    content_type=content_type,
                    metadata={**metadata},
                )
            )
            words = current.split()
            overlap_words = words[-chunk_overlap:] if chunk_overlap < len(words) else words
            current = " ".join(overlap_words) + "\n\n" + para
            position += len(current)
        else:
            current = (current + "\n\n" + para) if current else para

    if current.strip():
        chunks.append(
            Chunk(
                text=current.strip(),
                index=len(chunks),
                start_char=position,
                end_char=position + len(current),
                content_type=content_type,
                metadata={**metadata},
            )
        )

    return chunks


def _simple_split(text: str, config: ChunkingConfig) -> list[Chunk]:
    """Fallback simple split for texts without headers."""
    words = text.split()
    if not words:
        return []

    chunk_size_words = max(1, config.chunk_size * 3 // 4)
    overlap_words = max(0, config.chunk_overlap * 3 // 4)
    chunks: list[Chunk] = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size_words, len(words))
        chunk_words = words[start:end]
        chunks.append(
            Chunk(
                text=" ".join(chunk_words),
                index=len(chunks),
                start_char=0,
                end_char=len(" ".join(chunk_words)),
                content_type="generic",
                metadata={},
            )
        )
        if end >= len(words):
            break
        advance = max(chunk_size_words - overlap_words, 1)
        start += advance

    return chunks
