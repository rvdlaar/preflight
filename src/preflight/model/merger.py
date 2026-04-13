"""
Merge Strategy — deduplicate Preflight model against existing Archi model.

Before creating elements via MCP, we search the existing Archi model for matches:
- Exact name + type match → skip creation, reference existing
- Name match, different type → flag for architect review
- No match → create new

This prevents model pollution and respects the architect's existing work.

Thinking applied:
  First principles: The architect has 668+ elements. We don't want duplicates.
  Search before create. If it exists, reuse it.
  Second order: A name match across types might be the same real-world thing
  modeled differently (e.g., 'HIS' as ApplicationComponent vs ApplicationService).
  Flag these, don't auto-change — the architect decides.
  Inversion: What if the existing model has wrong/different naming? We search
  by substring, not exact match. But we prefer exact match for dedup. The architect
  can override via corrections.yaml.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    RelationshipType,
)
from preflight.model.archi_client import ArchiMCPClient

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    created_elements: int = 0
    reused_elements: int = 0
    flagged_elements: int = 0
    created_relationships: int = 0
    reused_relationships: int = 0
    skipped_relationships: int = 0
    details: list[str] = field(default_factory=list)

    @property
    def total_elements(self) -> int:
        return self.created_elements + self.reused_elements + self.flagged_elements

    @property
    def total_relationships(self) -> int:
        return self.created_relationships + self.reused_relationships + self.skipped_relationships


# ArchiMate type name mapping: our enum → Archi's EClass names
# Archi uses the same names as our ElementType values (e.g., "ApplicationComponent")
ETYPE_MAP = {et.value: et for et in ElementType}


async def merge_model_to_archi(
    model: ArchiMateModel,
    client: ArchiMCPClient,
    approval_mode: bool = True,
    batch: bool = True,
    view_name: str | None = None,
) -> MergeResult:
    """Merge an ArchiMateModel into the live Archi model via MCP.

    Strategy:
    1. For each element, search existing model. Reuse exact matches, flag type mismatches.
    2. For each relationship, check if it already exists between the same elements.
    3. Create view and place elements if view_name is provided.
    4. If approval_mode, set approval mode so architect reviews each mutation.

    Returns MergeResult with counts and details.
    """
    result = MergeResult()

    if approval_mode:
        await client.set_approval_mode(True)
        result.details.append("Approval mode enabled — architect will review each mutation")

    if batch:
        await client.begin_batch(description=f"Preflight merge: {model.name}")

    existing_id_map: dict[str, str] = {}
    name_type_map: dict[str, str] = {}

    try:
        for elem in model.elements:
            archi_type = elem.type.value
            search_results = await client.search_elements(query=elem.name, type=archi_type, limit=5)

            exact_match = None
            for sr in search_results:
                sr_name = sr.get("name", "")
                sr_type = sr.get("type", "")
                if sr_name.strip().lower() == elem.name.strip().lower() and sr_type == archi_type:
                    exact_match = sr
                    break

            if exact_match:
                archi_id = exact_match.get("id", "")
                existing_id_map[elem.id] = archi_id
                name_type_map[elem.name] = archi_id
                result.reused_elements += 1
                result.details.append(
                    f"REUSE: '{elem.name}' ({archi_type}) — existing id={archi_id}"
                )
                continue

            name_matches = await client.search_elements(query=elem.name, limit=5)
            type_mismatch = None
            for sr in name_matches:
                sr_name = sr.get("name", "").strip().lower()
                sr_type = sr.get("type", "")
                if sr_name == elem.name.strip().lower() and sr_type != archi_type:
                    type_mismatch = sr
                    break

            if type_mismatch:
                archi_id = type_mismatch.get("id", "")
                existing_id_map[elem.id] = archi_id
                name_type_map[elem.name] = archi_id
                result.flagged_elements += 1
                result.details.append(
                    f"FLAG: '{elem.name}' exists as {type_mismatch.get('type')} "
                    f"(expected {archi_type}) — reusing id={archi_id}"
                )
                continue

            props = dict(elem.properties)
            props["preflight:why"] = elem.why
            props["preflight:psa_id"] = model.psa_id

            create_result = await client.get_or_create_element(
                type=archi_type,
                name=elem.name,
                documentation=elem.documentation or "",
                properties=props,
            )

            if create_result.success:
                created_data = create_result.data or {}
                archi_id = created_data.get("id", created_data.get("elementId", ""))
                existing_id_map[elem.id] = archi_id
                name_type_map[elem.name] = archi_id
                result.created_elements += 1
                result.details.append(f"CREATE: '{elem.name}' ({archi_type}) — new id={archi_id}")
            else:
                result.details.append(
                    f"ERROR: Failed to create '{elem.name}' ({archi_type}): {create_result.error}"
                )

        for rel in model.relationships:
            source_archi_id = existing_id_map.get(rel.source_id, rel.source_id)
            target_archi_id = existing_id_map.get(rel.target_id, rel.target_id)

            rel_type_xsi = rel.xsi_type

            props = dict(rel.properties)
            props["preflight:why"] = rel.why

            create_result = await client.create_relationship(
                type=rel_type_xsi,
                source_id=source_archi_id,
                target_id=target_archi_id,
                name=rel.name or "",
                documentation=rel.documentation or "",
                properties=props,
            )

            if create_result.success:
                result.created_relationships += 1
                result.details.append(
                    f"CREATE REL: {rel_type_xsi} {source_archi_id} → {target_archi_id}"
                )
            else:
                err = create_result.error or ""
                if "already exists" in err.lower() or "duplicate" in err.lower():
                    result.reused_relationships += 1
                    result.details.append(f"REUSE REL: {rel_type_xsi} (already exists)")
                else:
                    result.skipped_relationships += 1
                    result.details.append(
                        f"SKIP REL: {rel_type_xsi} {source_archi_id} → {target_archi_id}: {err}"
                    )

        if view_name:
            view_result = await client.create_view(name=view_name)
            if view_result.success:
                view_data = view_result.data or {}
                view_id = view_data.get("id", view_data.get("viewId", ""))
                if view_id:
                    result.details.append(f"VIEW: Created '{view_name}' (id={view_id})")
                    for elem_id in existing_id_map.values():
                        await client.add_to_view(view_id, elem_id)
                    for rel in model.relationships:
                        pass

                    await client.auto_layout_and_route(view_id, mode="grouped")
                    result.details.append("LAYOUT: Auto-layout and routing applied")

    finally:
        if batch:
            await client.end_batch(rollback=False)
            result.details.append("Batch committed")

    return result
