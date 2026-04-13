"""
ArchiMate .archimate XML parser and query engine.

Traverses the hospital's Archi model to produce structured data for:
  - Step 0: Landscape context
  - Step 2: Per-persona scoped retrieval
  - Step 4: STRIDE pre-fill
  - Step 5: Diagrams / cascade dependencies
  - BIV: Cascade impact analysis

Also loads ZiRA reference model and surfaces conflicts.
"""

from preflight.archimate.parser import (
    parse_archimate,
    parse_archimate_xml,
    ArchiMateModel,
    ArchiElement,
    ArchiRelationship,
)
from preflight.archimate.query import (
    find_applications_by_capability,
    find_interfaces,
    find_cascade_dependencies,
    find_data_objects,
    build_landscape_context,
)
from preflight.archimate.stride import generate_stride_prefill
from preflight.archimate.zira import detect_zira_conflicts

__all__ = [
    "parse_archimate",
    "parse_archimate_xml",
    "ArchiMateModel",
    "ArchiElement",
    "ArchiRelationship",
    "find_applications_by_capability",
    "find_interfaces",
    "find_cascade_dependencies",
    "find_data_objects",
    "build_landscape_context",
    "generate_stride_prefill",
    "detect_zira_conflicts",
]
