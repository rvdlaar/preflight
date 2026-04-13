"""
LeanIX integration — application portfolio connector.

Fetches: application landscape, application fact sheets, subscription data.
Pushes: assessment tagging on LeanIX fact sheets.

API reference: https://docs.leanix.net/

Authentication: Bearer token via Authorization header.
Rate limit: 60 requests/minute (LeanIX standard).
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

LEANIX_GRAPHQL_URL_SUFFIX = "/services/pathfinder/v1/graphql"


class LeanIXClient(IntegrationClient):
    source = "leanix"
    rate_limit_per_second: float = 1.0

    def __init__(
        self,
        base_url: str = "https://eu.leanix.net",
        api_key: str | None = None,
        tenant: str | None = None,
        workspace_id: str | None = None,
    ):
        super().__init__(base_url, api_key, tenant)
        self.workspace_id = workspace_id

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _graphql_url(self) -> str:
        return f"{self.base_url}{LEANIX_GRAPHQL_URL_SUFFIX}"

    async def health(self) -> IntegrationResult:
        await self._rate_limited()
        try:
            query = '{ factSheetCount(type: "Application") }'
            async with self._http_request(timeout=10.0) as client:
                resp = await client.post(
                    self._graphql_url(),
                    json={"query": query},
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    count = data.get("data", {}).get("factSheetCount", 0)
                    return IntegrationResult(
                        status=IntegrationStatus.SUCCESS,
                        source=self.source,
                        data={"connected": True, "application_count": count},
                    )
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    source=self.source,
                    error=f"LeanIX health check returned {resp.status_code}",
                    metadata={"status_code": resp.status_code},
                )
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                source=self.source,
                error=str(e),
            )

    async def fetch(self, query: str, **kwargs: Any) -> IntegrationResult:
        fact_sheet_type = kwargs.get("fact_sheet_type", "Application")
        limit = kwargs.get("limit", 200)

        graphql_query = """
        query($filter: FilterInput!, $page: PageInput) {
          factSheets(filter: $filter, page: $page) {
            edges { node { id displayName type lifecycle { phase } } }
            totalCount
          }
        }
        """
        variables = {
            "filter": {
                "type": fact_sheet_type,
                "search": query,
            },
            "page": {"first": limit},
        }

        await self._rate_limited()
        try:
            async with self._http_request(timeout=30.0) as client:
                resp = await client.post(
                    self._graphql_url(),
                    json={"query": graphql_query, "variables": variables},
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
                        error="LeanIX rate limit exceeded",
                        metadata={"retry_after": resp.headers.get("Retry-After", "60")},
                    )

                resp.raise_for_status()
                result = resp.json()

                edges = result.get("data", {}).get("factSheets", {}).get("edges", [])
                items = [self.normalize(edge.get("node", {})) for edge in edges]
                total = result.get("data", {}).get("factSheets", {}).get("totalCount", len(items))

                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    source=self.source,
                    data={
                        "query": query,
                        "fact_sheet_type": fact_sheet_type,
                        "limit": limit,
                        "items": items,
                        "total": total,
                    },
                    metadata={"connected": True, "status_code": resp.status_code},
                )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"LeanIX fetch failed: {e}")
            return IntegrationResult(
                status=IntegrationStatus.PARTIAL,
                source=self.source,
                data={
                    "query": query,
                    "fact_sheet_type": fact_sheet_type,
                    "limit": limit,
                    "items": [],
                    "note": f"LeanIX fetch failed: {e}",
                },
                metadata={"connected": False},
            )

    async def push(self, data: dict[str, Any], **kwargs: Any) -> IntegrationResult:
        fact_sheet_id = kwargs.get("fact_sheet_id")

        if not fact_sheet_id:
            return IntegrationResult(
                status=IntegrationStatus.FAILED,
                source=self.source,
                error="fact_sheet_id required for push",
            )

        mutation = """
        mutation($id: ID!, $patches: [PatchInput!]!) {
          updateFactSheet(id: $id, patches: $patches, validateOnly: false) {
            factSheet { id displayName }
          }
        }
        """
        patches = [
            {
                "op": "replace",
                "path": f"/tags/{data.get('tag', 'assessed')}",
                "value": data.get("assessment_status", "assessed"),
            }
        ]
        if data.get("notes"):
            patches.append(
                {
                    "op": "add",
                    "path": "/notes",
                    "value": data["notes"],
                }
            )

        variables = {"id": fact_sheet_id, "patches": patches}

        await self._rate_limited()
        try:
            async with self._http_request(timeout=30.0) as client:
                resp = await client.post(
                    self._graphql_url(),
                    json={"query": mutation, "variables": variables},
                    headers=self._headers(),
                )

                if resp.status_code in (200, 201):
                    result = resp.json()
                    fs = result.get("data", {}).get("updateFactSheet", {}).get("factSheet", {})
                    return IntegrationResult(
                        status=IntegrationStatus.SUCCESS,
                        source=self.source,
                        data={
                            "fact_sheet_id": fact_sheet_id,
                            "tag": data.get("tag", "assessed"),
                            "external_id": fs.get("id", fact_sheet_id),
                            "status": "updated",
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
                        "fact_sheet_id": fact_sheet_id,
                        "tag": data.get("tag", "assessed"),
                        "external_id": None,
                        "note": f"LeanIX push returned {resp.status_code}",
                    },
                    metadata={"connected": False, "status_code": resp.status_code},
                )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"LeanIX push failed: {e}")
            return IntegrationResult(
                status=IntegrationStatus.PARTIAL,
                source=self.source,
                data={
                    "fact_sheet_id": fact_sheet_id,
                    "tag": data.get("tag", "assessed"),
                    "external_id": None,
                    "note": f"LeanIX push failed: {e}",
                },
                metadata={"connected": False},
            )

    def normalize(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return {
                "source_id": raw.get("id", ""),
                "name": raw.get("displayName", raw.get("name", "")),
                "type": raw.get("type", ""),
                "status": raw.get("lifecycle", {}).get("phase", ""),
                "business_criticality": raw.get("businessCriticality", ""),
                "application_risk": raw.get("riskValue", None),
                "subscriptions": raw.get("subscriptions", []),
            }
        return {"raw": raw}
