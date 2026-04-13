"""
TOPdesk integration — CMDB/ITSM/GRC connector.

Fetches: asset records, incident history, change records, SLA data.
Pushes: assessment results as TOPdesk change records.

API reference: https://developers.topdesk.com/

Authentication: Bearer token via Authorization header.
Rate limit: 100 requests/minute (TOPdesk default).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from preflight.integrations.base import (
    IntegrationClient,
    IntegrationResult,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

TOPDESK_API_PATHS = {
    "assets": "/api/incidentManagement/v3/assets",
    "applications": "/api/incidentManagement/v3/assets",
    "incidents": "/api/incidentManagement/v3/incidents",
    "changes": "/api/incidentManagement/v3/changes",
    "persons": "/api/incidentManagement/v3/persons",
    "operational_changes": "/api/incidentManagement/v3/changes",
}


class TOPdeskClient(IntegrationClient):
    source = "topdesk"
    rate_limit_per_second: float = 1.6  # 100/min

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        tenant: str | None = None,
        application_name: str = "Preflight",
    ):
        super().__init__(base_url, api_key, tenant)
        self.application_name = application_name

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def health(self) -> IntegrationResult:
        await self._rate_limited()
        try:
            async with self._http_request(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/incidentManagement/v3/settings",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return IntegrationResult(
                        status=IntegrationStatus.SUCCESS,
                        source=self.source,
                        data={"connected": True, "status": "healthy"},
                    )
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    source=self.source,
                    error=f"TOPdesk health check returned {resp.status_code}",
                    metadata={"status_code": resp.status_code},
                )
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                source=self.source,
                error=str(e),
            )

    async def fetch(self, query: str, **kwargs: Any) -> IntegrationResult:
        asset_type = kwargs.get("asset_type", "application")
        limit = kwargs.get("limit", 100)

        path = TOPDESK_API_PATHS.get(asset_type, TOPDESK_API_PATHS["assets"])
        params: dict[str, Any] = {
            "q": query,
            "$top": limit,
        }
        if asset_type == "application":
            params["type"] = "Application"

        await self._rate_limited()
        try:
            async with self._http_request(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.base_url}{path}",
                    params=params,
                    headers=self._headers(),
                )

                if resp.status_code == 401:
                    return IntegrationResult(
                        status=IntegrationStatus.FAILED,
                        source=self.source,
                        error="Authentication failed — check API key",
                        metadata={"status_code": 401},
                    )

                if resp.status_code == 429:
                    return IntegrationResult(
                        status=IntegrationStatus.RATE_LIMITED,
                        source=self.source,
                        error="TOPdesk rate limit exceeded",
                        metadata={"retry_after": resp.headers.get("Retry-After", "60")},
                    )

                resp.raise_for_status()
                data = resp.json()

                items = (
                    data if isinstance(data, list) else data.get("dataSet", data.get("results", []))
                )

                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    source=self.source,
                    data={
                        "query": query,
                        "asset_type": asset_type,
                        "limit": limit,
                        "items": [self.normalize(item) for item in items],
                        "total": len(items),
                    },
                    metadata={"connected": True, "status_code": resp.status_code},
                )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"TOPdesk fetch failed: {e}")
            return IntegrationResult(
                status=IntegrationStatus.PARTIAL,
                source=self.source,
                data={
                    "query": query,
                    "asset_type": asset_type,
                    "limit": limit,
                    "items": [],
                    "note": f"TOPdesk fetch failed: {e}",
                },
                metadata={"connected": False},
            )

    async def push(self, data: dict[str, Any], **kwargs: Any) -> IntegrationResult:
        change_type = kwargs.get("change_type", "request_for_change")

        payload = {
            "briefDescription": data.get(
                "title", data.get("briefDescription", "Preflight Assessment")
            ),
            "request": data.get("description", data.get("request", "")),
            "changeType": change_type,
            "status": data.get("status", "draft"),
            "category": data.get("category", "Information"),
            "subcategory": data.get("subcategory", "Architecture"),
            "externalNumber": data.get("assessment_id", ""),
        }

        await self._rate_limited()
        try:
            async with self._http_request(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}{TOPDESK_API_PATHS['changes']}",
                    json=payload,
                    headers=self._headers(),
                )

                if resp.status_code in (200, 201):
                    result = resp.json()
                    return IntegrationResult(
                        status=IntegrationStatus.SUCCESS,
                        source=self.source,
                        data={
                            "change_type": change_type,
                            "external_id": result.get("id", result.get("number", "")),
                            "status": "created",
                        },
                        metadata={"connected": True, "status_code": resp.status_code},
                    )

                if resp.status_code == 401:
                    return IntegrationResult(
                        status=IntegrationStatus.FAILED,
                        source=self.source,
                        error="Authentication failed — check API key",
                        metadata={"status_code": 401},
                    )

                return IntegrationResult(
                    status=IntegrationStatus.PARTIAL,
                    source=self.source,
                    data={
                        "change_type": change_type,
                        "external_id": None,
                        "note": f"TOPdesk push returned {resp.status_code}",
                    },
                    metadata={"connected": False, "status_code": resp.status_code},
                )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"TOPdesk push failed: {e}")
            return IntegrationResult(
                status=IntegrationStatus.PARTIAL,
                source=self.source,
                data={
                    "change_type": change_type,
                    "external_id": None,
                    "note": f"TOPdesk push failed: {e}",
                },
                metadata={"connected": False},
            )

    def normalize(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return {
                "source_id": raw.get("id", ""),
                "name": raw.get("name", raw.get("nasName", "")),
                "type": raw.get("type", raw.get("assetType", "")),
                "status": raw.get("status", ""),
                "vendor": raw.get("supplier", ""),
                "biv_b": raw.get("businessImpact", None),
                "last_incident": raw.get("lastIncidentDate", None),
            }
        return {"raw": raw}
