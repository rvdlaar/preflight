"""STRIDE threat model pre-fill from ArchiMate model components."""

from __future__ import annotations

from datetime import datetime, timezone

from preflight.archimate.parser import ArchiMateModel
from preflight.archimate.query import (
    find_interfaces,
    find_data_objects,
    find_cascade_dependencies,
)


def generate_stride_prefill(model: ArchiMateModel, application_id: str) -> dict | None:
    app = model.elements.get(application_id)
    if not app:
        return None

    interfaces = find_interfaces(model, application_id)
    data_objects = find_data_objects(model, application_id)
    cascade = find_cascade_dependencies(model, application_id, max_hops=1)

    threats: dict[str, list[dict]] = {
        "Spoofing": [],
        "Tampering": [],
        "Repudiation": [],
        "InformationDisclosure": [],
        "DenialOfService": [],
        "ElevationOfPrivilege": [],
    }

    for iface in interfaces:
        threats["Spoofing"].append(
            {
                "component": f"{app.name} → {iface['otherName']} ({iface['direction']} {iface['type']})",
                "finding": f"{'Incoming' if iface['direction'] == 'inbound' else 'Outgoing'} {iface['type']} relationship with {iface['otherName']} — verify authentication",
                "risk": "H" if iface["type"] == "Flow" else "M",
                "mitigation": f"Verify authentication mechanism for {iface['direction']} {iface['type']} to {iface['otherName']}",
            }
        )

    for dof in data_objects:
        threats["Tampering"].append(
            {
                "component": dof["name"],
                "finding": f"Application has {dof['accessType']} access to {dof['name']} (classification: {dof['classification']})",
                "risk": "H"
                if dof["classification"].lower()
                in (
                    "bijzondere persoonsgegevens",
                    "confidential",
                    "geheim",
                )
                else "M",
                "mitigation": f"Implement integrity controls for {dof['accessType']} access to {dof['name']}",
            }
        )

    if any(
        "persoon" in d["classification"].lower()
        or "patient" in d["classification"].lower()
        for d in data_objects
    ):
        threats["Repudiation"].append(
            {
                "component": f"{app.name} data access",
                "finding": "Application accesses personal/patient data — NEN 7513 audit logging required",
                "risk": "H",
                "mitigation": "Implement NEN 7513 compliant audit logging for all data access events",
            }
        )

    sensitive = [
        d
        for d in data_objects
        if d["classification"].lower()
        in (
            "bijzondere persoonsgegevens",
            "persoonsgegevens",
            "confidential",
            "geheim",
        )
    ]
    if sensitive:
        threats["InformationDisclosure"].append(
            {
                "component": f"{app.name} data handling",
                "finding": f"Application handles {len(sensitive)} sensitive data object(s): {', '.join(d['name'] for d in sensitive)}",
                "risk": "H",
                "mitigation": "Verify encryption at rest and in transit for all sensitive data",
            }
        )

    if cascade["direct"]:
        threats["DenialOfService"].append(
            {
                "component": f"{app.name} availability",
                "finding": f"{len(cascade['direct'])} downstream system(s) depend on this application: {', '.join(d['name'] for d in cascade['direct'])}",
                "risk": "H"
                if any(d["type"] == "ApplicationComponent" for d in cascade["direct"])
                else "M",
                "mitigation": "Implement rate limiting, health checks, and circuit breakers for downstream consumers",
            }
        )

    threats["ElevationOfPrivilege"].append(
        {
            "component": f"{app.name} authorization",
            "finding": "Role model and privilege separation to be reviewed — verify least-privilege access",
            "risk": "M",
            "mitigation": "Implement RBAC with least-privilege roles. Verify no shared service accounts with elevated privileges.",
        }
    )

    return {
        "application": {"id": application_id, "name": app.name},
        "interfaceCount": len(interfaces),
        "dataObjectCount": len(data_objects),
        "downstreamCount": len(cascade["direct"]),
        "threats": threats,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "draft": True,
    }
