"""Query engine for ArchiMate models — answer specific questions."""

from __future__ import annotations

from typing import Optional

from preflight.archimate.parser import ArchiMateModel, ArchiElement


def _related_targets(
    model: ArchiMateModel, element_id: str, rel_type: str
) -> list[str]:
    return [
        r.target
        for r in model.relationships
        if r.source == element_id and r.type == rel_type
    ]


def find_applications_by_capability(
    model: ArchiMateModel,
    capability_keywords: list[str],
) -> list[dict]:
    keywords = [k.lower() for k in capability_keywords]
    results: list[dict] = []

    for elem in model.elements.values():
        if elem.type != "ApplicationComponent":
            continue

        served_fn_ids = [
            t
            for t in _related_targets(model, elem.id, "Serving")
            if model.elements.get(t) and model.elements[t].type == "BusinessFunction"
        ]

        matches = any(
            kw in elem.name.lower()
            or any(kw in v.lower() for v in elem.properties.values())
            or any(
                kw
                in (model.elements[fid].name.lower() if fid in model.elements else "")
                for fid in served_fn_ids
            )
            for kw in keywords
        )

        if matches:
            results.append(
                {
                    "id": elem.id,
                    "name": elem.name,
                    "properties": elem.properties,
                    "lifecycle": elem.properties.get(
                        "Lifecycle status", elem.properties.get("Status", "unknown")
                    ),
                    "businessFunctions": [
                        model.elements[fid].name
                        for fid in served_fn_ids
                        if fid in model.elements
                    ],
                }
            )

    return results


def find_interfaces(model: ArchiMateModel, application_id: str) -> list[dict]:
    interfaces: list[dict] = []
    for rel in model.relationships:
        if rel.type not in ("Serving", "Flow", "Access"):
            continue
        is_source = rel.source == application_id
        is_target = rel.target == application_id
        if not is_source and not is_target:
            continue
        other_id = rel.target if is_source else rel.source
        other = model.elements.get(other_id)
        if not other:
            continue
        interfaces.append(
            {
                "direction": "outbound" if is_source else "inbound",
                "type": rel.type,
                "otherId": other_id,
                "otherName": other.name,
                "otherType": other.type,
            }
        )
    return interfaces


def find_cascade_dependencies(
    model: ArchiMateModel,
    application_id: str,
    max_hops: int = 3,
) -> dict:
    visited = {application_id}
    result: dict[str, list[dict]] = {"direct": [], "indirect": []}
    frontier = [application_id]
    hop = 0

    while frontier and hop < max_hops:
        hop += 1
        next_frontier: list[str] = []
        for fid in frontier:
            for rel in model.relationships:
                if rel.source != fid:
                    continue
                if rel.target in visited:
                    continue
                if rel.type not in ("Serving", "Flow", "Triggering", "Access"):
                    continue
                target = model.elements.get(rel.target)
                if not target:
                    continue
                visited.add(rel.target)
                next_frontier.append(rel.target)
                entry = {
                    "id": rel.target,
                    "name": target.name,
                    "type": target.type,
                    "layer": target.layer,
                    "relationship": rel.type,
                    "hop": hop,
                }
                result["direct" if hop == 1 else "indirect"].append(entry)
        frontier = next_frontier

    return result


def find_data_objects(model: ArchiMateModel, application_id: str) -> list[dict]:
    data_objects: list[dict] = []
    for rel in model.relationships:
        if rel.source != application_id and rel.target != application_id:
            continue
        if rel.type not in ("Access", "Flow"):
            continue
        other_id = rel.target if rel.source == application_id else rel.source
        other = model.elements.get(other_id)
        if not other or other.type != "DataObject":
            continue
        data_objects.append(
            {
                "id": other.id,
                "name": other.name,
                "accessType": "write" if rel.source == application_id else "read",
                "classification": other.properties.get(
                    "Classification", other.properties.get("Classificatie", "unknown")
                ),
            }
        )
    return data_objects


def build_landscape_context(
    model: ArchiMateModel,
    proposal_keywords: list[str],
) -> dict:
    existing_apps = find_applications_by_capability(model, proposal_keywords)
    all_app_names = [a["name"] for a in existing_apps]

    interfaces: list[dict] = []
    data_objects: list[dict] = []
    cascade_deps: list[dict] = []

    for app in existing_apps:
        app_ifaces = find_interfaces(model, app["id"])
        app_data = find_data_objects(model, app["id"])
        app_cascade = find_cascade_dependencies(model, app["id"], max_hops=2)

        interfaces.extend(
            [
                {
                    "from": app["name"],
                    "to": i["otherName"],
                    "direction": i["direction"],
                    "type": i["type"],
                }
                for i in app_ifaces
            ]
        )

        data_objects.extend(
            [
                {
                    "heldBy": app["name"],
                    "name": d["name"],
                    "accessType": d["accessType"],
                    "classification": d["classification"],
                }
                for d in app_data
            ]
        )

        cascade_deps.extend(
            [
                {
                    "source": app["name"],
                    "target": d["name"],
                    "relationship": d["relationship"],
                }
                for d in app_cascade["direct"]
            ]
        )

    return {
        "existingApps": all_app_names,
        "relatedInterfaces": list(
            {f"{i['from']} →{i['type']}→ {i['to']}" for i in interfaces}
        ),
        "openRisks": [
            f"Sensitive data ({d['classification']}): {d['name']} accessed by {d['heldBy']}"
            for d in data_objects
            if d["classification"].lower()
            in ("bijzondere persoonsgegevens", "persoonsgegevens")
        ],
        "recentChanges": [],
        "techRadarStatus": ", ".join(
            f"{a['name']}: {a['lifecycle']}" for a in existing_apps
        )
        or "unknown",
        "capabilityMap": "; ".join(
            f"{a['name']} → {', '.join(a['businessFunctions'])}" for a in existing_apps
        )
        or "not found",
        "raw": {
            "existingApps": existing_apps,
            "interfaces": interfaces[:20],
            "dataObjects": data_objects,
            "cascadeDeps": cascade_deps[:15],
        },
    }
