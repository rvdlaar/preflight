"""ZiRA conflict detection — compare hospital model vs ZiRA reference."""

from __future__ import annotations

from preflight.archimate.parser import ArchiMateModel


def _build_serving_map(model: ArchiMateModel) -> dict[str, dict]:
    serving: dict[str, dict] = {}
    for rel in model.relationships:
        if rel.type not in ("Serving", "Realization"):
            continue
        source = model.elements.get(rel.source)
        target = model.elements.get(rel.target)
        if not source or not target:
            continue
        if target.type == "BusinessFunction" and source.layer == "Application":
            if rel.target not in serving:
                serving[rel.target] = {"name": target.name, "apps": []}
            serving[rel.target]["apps"].append({"id": source.id, "name": source.name})
    return serving


def detect_zira_conflicts(
    hospital_model: ArchiMateModel,
    zira_model: ArchiMateModel,
) -> list[dict]:
    hospital_serving = _build_serving_map(hospital_model)
    zira_serving = _build_serving_map(zira_model)

    conflicts: list[dict] = []

    for bf_id, bf_data in zira_serving.items():
        hospital_apps = hospital_serving.get(bf_id)
        zira_apps = bf_data.get("apps", [])

        if not zira_apps:
            continue

        if not hospital_apps and zira_apps:
            conflicts.append(
                {
                    "type": "missing",
                    "businessFunction": bf_data["name"],
                    "ziRAExpects": ", ".join(a["name"] for a in zira_apps),
                    "hospitalHas": "nothing",
                    "message": (
                        f'ZiRA expects business function "{bf_data["name"]}" to be served by '
                        f"{', '.join(a['name'] for a in zira_apps)}. No implementation found in hospital model."
                    ),
                }
            )
        elif hospital_apps:
            hospital_names = {a["name"].lower() for a in hospital_apps["apps"]}
            zira_names = {a["name"].lower() for a in zira_apps}
            mismatches = [
                a for a in hospital_apps["apps"] if a["name"].lower() not in zira_names
            ]
            if mismatches:
                conflicts.append(
                    {
                        "type": "mismatch",
                        "businessFunction": bf_data["name"],
                        "ziRAExpects": ", ".join(a["name"] for a in zira_apps),
                        "hospitalHas": ", ".join(
                            a["name"] for a in hospital_apps["apps"]
                        ),
                        "message": (
                            f'ZiRA says "{bf_data["name"]}" should be served by '
                            f"{', '.join(a['name'] for a in zira_apps)}. Hospital model shows "
                            f"{', '.join(a['name'] for a in hospital_apps['apps'])}."
                        ),
                    }
                )

    return conflicts
