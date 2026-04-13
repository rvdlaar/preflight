"""
Microsoft Graph integration — SharePoint/OneDrive document connector.

Fetches: policy documents, architecture records, compliance evidence.
Pushes: assessment reports to SharePoint library.

API reference: https://learn.microsoft.com/en-us/graph/

Authentication: Bearer token via Authorization header (Entra ID OAuth2).
Rate limit: varies by license, default ~10,000 requests/5min.
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


class GraphClient(IntegrationClient):
    source = "graph"
    rate_limit_per_second: float = 30.0

    def __init__(
        self,
        base_url: str = "https://graph.microsoft.com/v1.0",
        api_key: str | None = None,
        tenant: str | None = None,
        site_id: str | None = None,
        drive_id: str | None = None,
    ):
        super().__init__(base_url, api_key, tenant)
        self.site_id = site_id
        self.drive_id = drive_id

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _site_url(self) -> str:
        if self.site_id:
            return f"{self.base_url}/sites/{self.site_id}"
        return f"{self.base_url}/sites"

    def _drive_url(self) -> str:
        if self.drive_id:
            return f"{self.base_url}/drives/{self.drive_id}"
        if self.site_id:
            return f"{self._site_url()}/drive"
        return f"{self.base_url}/me/drive"

    async def health(self) -> IntegrationResult:
        await self._rate_limited()
        try:
            async with self._http_request(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/me",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    user = resp.json()
                    return IntegrationResult(
                        status=IntegrationStatus.SUCCESS,
                        source=self.source,
                        data={
                            "connected": True,
                            "status": "healthy",
                            "user": user.get("displayName", ""),
                        },
                    )
                return IntegrationResult(
                    status=IntegrationStatus.FAILED,
                    source=self.source,
                    error=f"Graph health check returned {resp.status_code}",
                    metadata={"status_code": resp.status_code},
                )
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            return IntegrationResult(
                status=IntegrationStatus.UNAVAILABLE,
                source=self.source,
                error=str(e),
            )

    async def fetch(self, query: str, **kwargs: Any) -> IntegrationResult:
        folder = kwargs.get("folder", "Documents")
        file_types = kwargs.get("file_types", [".pdf", ".docx", ".xlsx"])
        limit = kwargs.get("limit", 100)

        search_url = f"{self.base_url}/me/drive/root/search(q='{query}')"
        if self.site_id:
            search_url = f"{self._site_url()}/drive/root/search(q='{query}')"

        params: dict[str, str] = {"$top": str(limit)}
        if file_types:
            type_filter = " or ".join(f"fileType eq '{ft.lstrip('.')}'" for ft in file_types)
            params["$filter"] = type_filter

        await self._rate_limited()
        try:
            async with self._http_request(timeout=30.0) as client:
                resp = await client.get(
                    search_url,
                    params=params,
                    headers=self._headers(),
                )

                if resp.status_code == 401:
                    return IntegrationResult(
                        status=IntegrationStatus.FAILED,
                        source=self.source,
                        error="Authentication failed — check OAuth2 token",
                        metadata={"status_code": 401},
                    )

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "60")
                    return IntegrationResult(
                        status=IntegrationStatus.RATE_LIMITED,
                        source=self.source,
                        error="Graph rate limit exceeded",
                        metadata={"retry_after": retry_after},
                    )

                resp.raise_for_status()
                data = resp.json()

                items = [self.normalize(item) for item in data.get("value", [])]

                return IntegrationResult(
                    status=IntegrationStatus.SUCCESS,
                    source=self.source,
                    data={
                        "query": query,
                        "folder": folder,
                        "file_types": file_types,
                        "items": items,
                        "total": len(items),
                    },
                    metadata={"connected": True, "status_code": resp.status_code},
                )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"Graph fetch failed: {e}")
            return IntegrationResult(
                status=IntegrationStatus.PARTIAL,
                source=self.source,
                data={
                    "query": query,
                    "folder": folder,
                    "file_types": file_types,
                    "items": [],
                    "note": f"Graph fetch failed: {e}",
                },
                metadata={"connected": False},
            )

    async def push(self, data: dict[str, Any], **kwargs: Any) -> IntegrationResult:
        folder = kwargs.get("folder", "Assessments")
        file_name = data.get("file_name", "assessment.md")
        content = data.get("content", "")

        upload_url = f"{self._drive_url()}/root:/{folder}/{file_name}:/content"

        headers = self._headers()
        headers["Content-Type"] = "text/plain"

        await self._rate_limited()
        try:
            async with self._http_request(timeout=30.0) as client:
                resp = await client.put(
                    upload_url,
                    content=content.encode("utf-8"),
                    headers=headers,
                )

                if resp.status_code in (200, 201):
                    result = resp.json()
                    return IntegrationResult(
                        status=IntegrationStatus.SUCCESS,
                        source=self.source,
                        data={
                            "folder": folder,
                            "file_name": file_name,
                            "external_id": result.get("id", ""),
                            "url": result.get("webUrl", ""),
                            "status": "uploaded",
                        },
                        metadata={"connected": True, "status_code": resp.status_code},
                    )

                if resp.status_code == 401:
                    return IntegrationResult(
                        status=IntegrationStatus.FAILED,
                        source=self.source,
                        error="Authentication failed — check OAuth2 token",
                        metadata={"status_code": 401},
                    )

                return IntegrationResult(
                    status=IntegrationStatus.PARTIAL,
                    source=self.source,
                    data={
                        "folder": folder,
                        "file_name": file_name,
                        "external_id": None,
                        "note": f"Graph push returned {resp.status_code}",
                    },
                    metadata={"connected": False, "status_code": resp.status_code},
                )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"Graph push failed: {e}")
            return IntegrationResult(
                status=IntegrationStatus.PARTIAL,
                source=self.source,
                data={
                    "folder": folder,
                    "file_name": file_name,
                    "external_id": None,
                    "note": f"Graph push failed: {e}",
                },
                metadata={"connected": False},
            )

    def normalize(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return {
                "source_id": raw.get("id", ""),
                "name": raw.get("name", ""),
                "type": raw.get("file", {}).get("mimeType", ""),
                "url": raw.get("webUrl", ""),
                "modified": raw.get("lastModifiedDateTime", ""),
                "size": raw.get("size", 0),
            }
        return {"raw": raw}
