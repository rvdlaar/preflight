"""
Preflight experiment config — the "train.py" that the agent modifies.

All tunable pipeline parameters live here. The agent edits this file,
the runner reads it, and experiments are measured against ground-truth QA.

Sections:
  PDF_PARSING    — how PDFs are converted to structured markdown
  CHUNKING       — child/parent chunk sizes, overlap, strategy
  EMBEDDING      — model, dimensions, batch size, routing
  RETRIEVAL      — alpha, top_k, reranking, parent document expansion
  VERSIONING     — version tag behaviour, conflict handling
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_FILE = PROJECT_ROOT / "experiment" / "config.json"

_REGISTRY: dict[str, Any] = {}


def get_registry() -> dict[str, Any]:
    return _REGISTRY


def set_registry_value(key: str, value: Any) -> None:
    _REGISTRY[key] = value


def apply_config(config: PipelineConfig) -> None:
    """Apply config to the shared registry.

    Modules that read from _REGISTRY at call time (rather than at import time)
    will pick up config changes dynamically. Modules that imported module-level
    constants before apply_config() is called will NOT see the changes.
    Log a warning about this limitation.
    """
    set_registry_value("chunking_child_size", config.chunking.child_chunk_size)
    set_registry_value("chunking_child_overlap", config.chunking.child_overlap)
    set_registry_value("retrieval_alpha", config.retrieval.alpha)
    set_registry_value("retrieval_top_k", config.retrieval.top_k)
    set_registry_value("retrieval_reranker", config.retrieval.reranker)
    set_registry_value("retrieval_parent_expansion", config.retrieval.parent_expansion)
    set_registry_value("retrieval_min_score", config.retrieval.min_score)
    set_registry_value("pdf_engine", config.pdf.engine)
    set_registry_value("pdf_extract_tables", config.pdf.extract_tables)
    set_registry_value("versioning_default_tag", config.versioning.default_tag)
    set_registry_value("versioning_conflict_policy", config.versioning.conflict_policy)
    set_registry_value("versioning_filter_by_version", config.versioning.filter_by_version)
    set_registry_value("versioning_requested_version", config.versioning.requested_version)

    _REGISTRY["config"] = config

    logger.warning(
        "Config applied to registry. NOTE: modules that imported module-level "
        "constants BEFORE apply_config() was called will not see changes. "
        "For experiment config to take effect, re-import or use registry getters."
    )


@dataclass
class PDFParsingConfig:
    engine: str = "pymupdf"
    extract_tables: bool = True
    table_format: str = "markdown"
    extract_images: bool = False
    image_vision_model: str = ""
    page_timeout_seconds: int = 30
    marker_use_llm: bool = False
    marker_llm_model: str = ""


@dataclass
class ChunkingConfig:
    child_chunk_size: int = 512
    child_overlap: int = 77
    parent_chunk_size: int = 2048
    parent_overlap: int = 200
    strategy: str = "section_aware"
    preserve_tables: bool = True
    table_row_per_chunk: bool = True
    regulatory_chunk_size: int = 512
    vendor_chunk_size: int = 1024
    policy_chunk_size: int = 768


@dataclass
class EmbeddingConfig:
    model: str = "intfloat/multilingual-e5-small"
    dimensions: int = 384
    batch_size: int = 32
    router: str = "local"
    content_type_routing: bool = True


@dataclass
class RetrievalConfig:
    alpha: float = 0.5
    top_k: int = 15
    reranker: str = "identity"
    reranker_model: str = ""
    parent_expansion: bool = True
    parent_max_tokens: int = 2048
    persona_augmentation: bool = True
    hyde_enabled: bool = False
    min_score: float = 0.3


@dataclass
class VersioningConfig:
    default_tag: str = "latest"
    conflict_policy: str = "newer_wins"
    warn_on_conflict: bool = True
    filter_by_version: bool = False
    requested_version: str = ""


@dataclass
class PipelineConfig:
    pdf: PDFParsingConfig = field(default_factory=PDFParsingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    versioning: VersioningConfig = field(default_factory=VersioningConfig)


DEFAULT_CONFIG = PipelineConfig()


def load_config(path: str | None = None) -> PipelineConfig:
    config_path = Path(path) if path else CONFIG_FILE
    if not config_path.exists():
        return PipelineConfig()
    with open(config_path) as f:
        data = json.load(f)
    return PipelineConfig(
        pdf=PDFParsingConfig(**data.get("pdf", {})),
        chunking=ChunkingConfig(**data.get("chunking", {})),
        embedding=EmbeddingConfig(**data.get("embedding", {})),
        retrieval=RetrievalConfig(**data.get("retrieval", {})),
        versioning=VersioningConfig(**data.get("versioning", {})),
    )


def save_config(config: PipelineConfig, path: str | None = None) -> None:
    config_path = Path(path) if path else CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)


def config_diff(a: PipelineConfig, b: PipelineConfig) -> dict:
    """Return dict of fields that differ between two configs."""
    da, db = asdict(a), asdict(b)
    diff: dict = {}
    for section in da:
        if da[section] != db[section]:
            diff[section] = {
                k: (da[section][k], db[section][k])
                for k in da[section]
                if da[section][k] != db[section][k]
            }
    return diff
