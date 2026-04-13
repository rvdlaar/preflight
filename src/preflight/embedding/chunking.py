"""
Preflight chunking — document-type-aware chunk splitting.

Uses chonkie for semantic chunking when available (better boundary detection
for regulatory docs), falls back to recursive character splitting. ArchiMate
and tabular chunking are always custom (preserving graph/table structure).

Design decisions:
- Chunk size targets: 512 tokens regulatory, 1024 vendor docs, per-row tables
- Overlap: 15% for regulatory (don't split mid-clause), 10% for vendor docs
- Every chunk carries metadata: source, section, language, persona_relevance
- Bilingual boundary preservation: don't split mid-sentence across NL/EN
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CHONKIE_AVAILABLE = False
try:
    from chonkie import SemanticChunker as _ChonkieSemantic

    _CHONKIE_AVAILABLE = True
except ImportError:
    pass


@dataclass
class Chunk:
    text: str
    index: int
    start_char: int
    end_char: int
    content_type: str
    metadata: dict = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text.split()))


@dataclass
class ChunkingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 77
    separators: list[str] = field(
        default_factory=lambda: ["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " "]
    )
    min_chunk_size: int = 50


REGULATORY_CONFIG = ChunkingConfig(
    chunk_size=512,
    chunk_overlap=77,
    separators=["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " "],
    min_chunk_size=50,
)

VENDOR_CONFIG = ChunkingConfig(
    chunk_size=1024,
    chunk_overlap=102,
    separators=["\n\n## ", "\n\n### ", "\n\n#### ", "\n\n", "\n", ". ", " "],
    min_chunk_size=100,
)

POLICY_CONFIG = ChunkingConfig(
    chunk_size=768,
    chunk_overlap=115,
    separators=["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " "],
    min_chunk_size=80,
)


CONFIG_BY_TYPE = {
    "regulatory": REGULATORY_CONFIG,
    "vendor": VENDOR_CONFIG,
    "policy": POLICY_CONFIG,
    "archimate": ChunkingConfig(chunk_size=384, chunk_overlap=0, min_chunk_size=30),
    "tabular": ChunkingConfig(chunk_size=256, chunk_overlap=0, min_chunk_size=20),
    "generic": ChunkingConfig(chunk_size=512, chunk_overlap=77, min_chunk_size=50),
}


def chunk_text_semantic(
    text: str,
    content_type: str = "generic",
    chunk_size: int | None = None,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Semantic chunking via chonkie — respects sentence/paragraph boundaries.

    chonkie's SemanticChunker uses embedding similarity to find natural
    topic boundaries. For regulatory docs, this means never splitting
    mid-clause or mid-requirement. Falls back to chunk_text() if chonkie
    is unavailable or fails.
    """
    if not _CHONKIE_AVAILABLE or not text.strip():
        return chunk_text(text, content_type, metadata=metadata)

    cfg = CONFIG_BY_TYPE.get(content_type, ChunkingConfig())
    size = chunk_size or cfg.chunk_size
    meta = metadata or {}

    try:
        chunker = _ChonkieSemantic(chunk_size=size, overlap=cfg.chunk_overlap)
        chonkie_chunks = chunker.chunk(text)

        results: list[Chunk] = []
        for i, c in enumerate(chonkie_chunks):
            chunk_text_content = c.text if hasattr(c, "text") else str(c)
            if len(chunk_text_content.strip()) < cfg.min_chunk_size:
                continue
            results.append(
                Chunk(
                    text=chunk_text_content.strip(),
                    index=len(results),
                    start_char=getattr(c, "start_index", 0),
                    end_char=getattr(c, "end_index", len(chunk_text_content)),
                    content_type=content_type,
                    metadata={**meta},
                )
            )
        return results if results else chunk_text(text, content_type, metadata=meta)
    except Exception:
        return chunk_text(text, content_type, metadata=metadata)


def chunk_text(
    text: str,
    content_type: str = "generic",
    config: ChunkingConfig | None = None,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Split text into chunks using recursive character splitting.

    Tries to split at document-structure boundaries first (## headers),
    then paragraphs, then sentences, then words. Never splits mid-word.

    For semantic chunking with chonkie, use chunk_text_semantic() instead.
    """
    cfg = config or CONFIG_BY_TYPE.get(content_type, ChunkingConfig())
    meta = metadata or {}

    if not text.strip():
        return []

    sections = _split_by_structure(text, cfg)
    chunks: list[Chunk] = []
    position = 0

    for section in sections:
        if not section.strip():
            continue

        section_meta = {**meta}
        header_match = re.match(r"^#{1,4}\s+(.+)", section)
        if header_match:
            section_meta["section"] = header_match.group(1).strip()

        section_chunks = _split_section(section, cfg)
        for chunk_text_content in section_chunks:
            if len(chunk_text_content.strip()) < cfg.min_chunk_size:
                continue

            start = text.find(chunk_text_content, position)
            if start == -1:
                start = position

            chunks.append(
                Chunk(
                    text=chunk_text_content.strip(),
                    index=len(chunks),
                    start_char=start,
                    end_char=start + len(chunk_text_content),
                    content_type=content_type,
                    metadata={**section_meta},
                )
            )
            position = start + len(chunk_text_content)

    if not chunks and len(text.strip()) >= cfg.min_chunk_size:
        chunks.append(
            Chunk(
                text=text.strip(),
                index=0,
                start_char=0,
                end_char=len(text),
                content_type=content_type,
                metadata=meta,
            )
        )

    return chunks


def _split_by_structure(text: str, config: ChunkingConfig) -> list[str]:
    """Split text at header boundaries to preserve document structure."""
    header_pattern = re.compile(r"^#{1,4}\s+", re.MULTILINE)
    splits = header_pattern.split(text)

    if len(splits) <= 1:
        return [text]

    headers = header_pattern.findall(text)
    sections: list[str] = []

    if splits[0].strip():
        sections.append(splits[0])

    for i, header in enumerate(headers):
        content_idx = i + 1
        if content_idx < len(splits):
            section_text = header + splits[content_idx]
            if section_text.strip():
                sections.append(section_text)

    return sections


def _split_section(text: str, config: ChunkingConfig) -> list[str]:
    """Split a section into chunks of approximately config.chunk_size words."""
    words = text.split()
    if not words:
        return []

    chunk_size_words = max(1, config.chunk_size * 3 // 4)
    overlap_words = max(0, config.chunk_overlap * 3 // 4)

    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size_words, len(words))
        chunk_words = words[start:end]

        if chunk_size_words > 20 and end < len(words):
            last_period = -1
            for j in range(len(chunk_words) - 1, max(len(chunk_words) - 30, -1), -1):
                if chunk_words[j].rstrip().endswith((".", "!", "?", "。", "！", "？")):
                    last_period = j
                    break
            if last_period > 0:
                chunk_words = chunk_words[: last_period + 1]
                end = start + last_period + 1

        chunks.append(" ".join(chunk_words))

        if end >= len(words):
            break

        advance = max(chunk_size_words - overlap_words, 1)
        start += advance
        if start >= end:
            start = end

    return chunks


def chunk_tabular(
    rows: list[str],
    headers: list[str],
    source_id: str = "",
    metadata: dict | None = None,
) -> list[Chunk]:
    """Chunk tabular data — one row per chunk with headers repeated.

    Each chunk is a Markdown table row with column headers, making it
    independently interpretable (critical for RAG retrieval).
    """
    meta = metadata or {}
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join("-" * max(3, len(h)) for h in headers) + " |"

    chunks: list[Chunk] = []
    for i, row in enumerate(rows):
        chunk_text = f"{header_line}\n{separator_line}\n{row}"
        chunks.append(
            Chunk(
                text=chunk_text,
                index=i,
                start_char=0,
                end_char=len(chunk_text),
                content_type="tabular",
                metadata={
                    **meta,
                    "row_index": i,
                    "source_id": source_id,
                    "columns": headers,
                },
            )
        )

    return chunks


def chunk_archimate_elements(
    elements: list[dict],
    relationships: list[dict],
) -> list[Chunk]:
    """Chunk ArchiMate elements — one object per chunk with its relationships.

    Preserves graph structure: each chunk contains the element's properties
    and all its direct relationships. This makes elements retrievable by
    their role in the architecture, not just their name.
    """
    rel_by_source: dict[str, list[dict]] = {}
    rel_by_target: dict[str, list[dict]] = {}
    for rel in relationships:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        rel_by_source.setdefault(src, []).append(rel)
        rel_by_target.setdefault(tgt, []).append(rel)

    chunks: list[Chunk] = []
    for i, elem in enumerate(elements):
        elem_id = elem.get("id", "")
        elem_type = elem.get("type", "ApplicationComponent")
        elem_name = elem.get("name", "Unknown")
        elem_props = elem.get("properties", {})
        layer = elem.get("layer", "Application")

        parts = [f"[{layer}] {elem_type}: {elem_name}"]
        if elem_props:
            for k, v in elem_props.items():
                parts.append(f"  {k}: {v}")

        source_rels = rel_by_source.get(elem_id, [])
        target_rels = rel_by_target.get(elem_id, [])

        if source_rels:
            parts.append("  Serves / connects to:")
            for rel in source_rels:
                rel_type = rel.get("relationship_type", "Serving")
                target_name = rel.get("target_name", "unknown")
                parts.append(f"    - [{rel_type}] → {target_name}")

        if target_rels:
            parts.append("  Served by / connected from:")
            for rel in target_rels:
                rel_type = rel.get("relationship_type", "Serving")
                source_name = rel.get("source_name", "unknown")
                parts.append(f"    - [{rel_type}] ← {source_name}")

        chunk_text = "\n".join(parts)
        chunks.append(
            Chunk(
                text=chunk_text,
                index=i,
                start_char=0,
                end_char=len(chunk_text),
                content_type="archimate",
                metadata={
                    "element_id": elem_id,
                    "element_type": elem_type,
                    "element_name": elem_name,
                    "layer": layer,
                    "source_id": f"archimate-{elem_id}",
                    "relationships": [
                        r.get("relationship_type", "")
                        for r in source_rels + target_rels
                    ],
                },
            )
        )

    return chunks
