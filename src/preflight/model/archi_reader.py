"""
Archi Reader — reads existing Archi model via MCP for pipeline grounding.

Replaces the landscape_context dict with live Archi data. The pipeline's
classification and retrieval steps become more accurate because they're
grounded in the actual model.

Thinking applied:
  First principles: The architect has a real model with real elements and
  relationships. We should use it. Search by relevant types, get relationships,
  structure the data for the pipeline.
  Second order: A 668-element model is big. We can't fetch everything.
  Search by query/type, limit results, and focus on what's relevant to the
  assessment request.
  Inversion: What if the model is empty? What if the server is down?
  We return empty data and fall through gracefully. The pipeline works
  without Archi — this just makes it better.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from preflight.model.archi_client import ArchiMCPClient

logger = logging.getLogger(__name__)


@dataclass
class ArchiLandscape:
    """Landscape data extracted from the live Archi model."""

    applications: list[dict[str, Any]] = field(default_factory=list)
    business_functions: list[dict[str, Any]] = field(default_factory=list)
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    principles: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    model_name: str = ""
    model_info: dict[str, Any] = field(default_factory=dict)


ARCHI_APP_TYPES = [
    "ApplicationComponent",
    "ApplicationService",
    "ApplicationInterface",
    "ApplicationFunction",
    "ApplicationCollaboration",
    "ApplicationProcess",
    "ApplicationEvent",
]

ARCHI_BUSINESS_TYPES = [
    "BusinessFunction",
    "BusinessProcess",
    "BusinessService",
    "BusinessActor",
    "BusinessRole",
    "BusinessObject",
]

ARCHI_MAPPING = {
    "applications": ARCHI_APP_TYPES,
    "business_functions": ["BusinessFunction", "BusinessProcess", "BusinessService"],
    "interfaces": ["ApplicationInterface", "TechnologyInterface", "ApplicationService"],
    "nodes": ["Node", "Device", "SystemSoftware", "TechnologyService"],
    "principles": ["Principle", "Requirement", "Constraint", "Goal", "Driver", "Assessment"],
}


async def read_archi_landscape(
    client: ArchiMCPClient,
    query: str | None = None,
    max_per_type: int = 50,
) -> ArchiLandscape:
    """Read the landscape from the live Archi model.

    If query is provided, search for elements matching that query.
    If query is None, fetch top elements per type.
    """
    landscape = ArchiLandscape()

    try:
        info = await client.get_model_info()
        landscape.model_name = info.get("name", "")
        landscape.model_info = info
    except Exception as e:
        logger.warning(f"Cannot read Archi model info: {e}")
        return landscape

    for category, type_names in ARCHI_MAPPING.items():
        for type_name in type_names:
            try:
                results = await client.search_elements(
                    query=query or "",
                    type=type_name,
                    limit=max_per_type,
                )
                for elem in results:
                    entry = {
                        "id": elem.get("id", ""),
                        "name": elem.get("name", ""),
                        "type": elem.get("type", type_name),
                        "documentation": elem.get("documentation", ""),
                        "properties": elem.get("properties", {}),
                    }
                    if category == "applications":
                        landscape.applications.append(entry)
                    elif category == "business_functions":
                        landscape.business_functions.append(entry)
                    elif category == "interfaces":
                        landscape.interfaces.append(entry)
                    elif category == "nodes":
                        landscape.nodes.append(entry)
                    elif category == "principles":
                        landscape.principles.append(entry)
            except Exception as e:
                logger.warning(f"Error searching {type_name}: {e}")
                continue

    try:
        landscape.relationships = await client.search_relationships(
            query=query or "", limit=max_per_type * 2
        )
    except Exception as e:
        logger.warning(f"Cannot read relationships: {e}")

    logger.info(
        f"Read Archi landscape: {len(landscape.applications)} apps, "
        f"{len(landscape.business_functions)} business functions, "
        f"{len(landscape.interfaces)} interfaces, "
        f"{len(landscape.nodes)} nodes, "
        f"{len(landscape.principles)} principles, "
        f"{len(landscape.relationships)} relationships"
    )

    return landscape


def landscape_to_context(landscape: ArchiLandscape) -> dict[str, Any]:
    """Convert ArchiLandscape to the pipeline's landscape_context dict format.

    This produces the same structure that _get_landscape() in builder.py
    expects, so the pipeline can consume Archi data seamlessly.
    """
    existing_apps = [
        {"name": app["name"], "id": app["id"], "type": app["type"]}
        for app in landscape.applications
    ]

    related_interfaces = [
        {"name": intf["name"], "id": intf["id"], "type": intf["type"]}
        for intf in landscape.interfaces
    ]

    business_functions = [
        {"name": bf["name"], "id": bf["id"]} for bf in landscape.business_functions
    ]

    principles = [
        {"name": p["name"], "id": p["id"], "type": p["type"]} for p in landscape.principles
    ]

    return {
        "source": "archi-mcp",
        "model_name": landscape.model_name,
        "existingApps": existing_apps,
        "relatedInterfaces": related_interfaces,
        "businessFunctions": business_functions,
        "principles": principles,
        "relationships": landscape.relationships,
    }
