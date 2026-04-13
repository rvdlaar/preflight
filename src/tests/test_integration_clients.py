"""
Tests for integration clients — TOPdesk, LeanIX, Graph.

Uses httpx.MockTransport injected via _http_client for deterministic testing.
Verifies: auth headers, error handling, normalize, health checks, fetch, push.
"""

from __future__ import annotations

import httpx
import pytest

from preflight.integrations.base import IntegrationClient, IntegrationResult, IntegrationStatus
from preflight.integrations.graph import GraphClient
from preflight.integrations.leanix import LeanIXClient
from preflight.integrations.topdesk import TOPDESK_API_PATHS, TOPdeskClient


def _inject_mock(client: IntegrationClient, handler) -> None:
    client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json_response(status_code: int = 200, json_data=None, headers=None):
    data = json_data or {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=data, headers=headers or {})

    return handler


class TestBaseIntegrationClient:
    def test_rate_limiter_default(self):
        client = IntegrationClient(base_url="https://example.com")
        assert client.rate_limit_per_second == 10.0

    def test_not_implemented(self):
        client = IntegrationClient(base_url="https://example.com")
        result = client._not_implemented("health")
        assert result.status == IntegrationStatus.UNAVAILABLE

    def test_result_ok_property(self):
        ok = IntegrationResult(status=IntegrationStatus.SUCCESS, source="test")
        assert ok.ok is True
        fail = IntegrationResult(status=IntegrationStatus.FAILED, source="test", error="x")
        assert fail.ok is False
        partial = IntegrationResult(status=IntegrationStatus.PARTIAL, source="test")
        assert partial.ok is True


class TestTOPdeskClient:
    def test_api_paths_correct(self):
        for key, path in TOPDESK_API_PATHS.items():
            assert "/incidentManagement/" in path, f"{key}: {path} has typo"

    def test_normalize_dict(self):
        client = TOPdeskClient(base_url="https://topdesk.example.com")
        result = client.normalize(
            {
                "id": "A-1",
                "name": "Sysmex",
                "type": "Application",
                "status": "prod",
                "supplier": "Sysmex",
            }
        )
        assert result["source_id"] == "A-1"
        assert result["name"] == "Sysmex"
        assert result["vendor"] == "Sysmex"

    def test_normalize_raw(self):
        client = TOPdeskClient(base_url="https://topdesk.example.com")
        assert client.normalize("string") == {"raw": "string"}

    def test_auth_headers(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="key-123")
        assert client._headers()["Authorization"] == "Bearer key-123"

    @pytest.mark.asyncio
    async def test_health_success(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="test")
        _inject_mock(client, _json_response(200, {}))
        result = await client.health()
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["connected"] is True

    @pytest.mark.asyncio
    async def test_health_failure(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="test")
        _inject_mock(client, _json_response(500, {}))
        result = await client.health()
        assert result.status == IntegrationStatus.FAILED

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="test")
        _inject_mock(
            client,
            _json_response(
                200,
                {
                    "dataSet": [
                        {"id": "1", "name": "Sysmex", "assetType": "Application", "status": "prod"},
                    ]
                },
            ),
        )
        result = await client.fetch("pathology")
        assert result.status == IntegrationStatus.SUCCESS
        assert len(result.data["items"]) == 1

    @pytest.mark.asyncio
    async def test_fetch_auth_failure(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="bad")
        _inject_mock(client, _json_response(401, {"error": "unauthorized"}))
        result = await client.fetch("test")
        assert result.status == IntegrationStatus.FAILED
        assert "401" in result.error or "Authentication" in result.error

    @pytest.mark.asyncio
    async def test_fetch_rate_limited(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="test")
        _inject_mock(client, _json_response(429, {}, headers={"Retry-After": "60"}))
        result = await client.fetch("test")
        assert result.status == IntegrationStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_push_success(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="test")
        _inject_mock(client, _json_response(201, {"id": "CHG-001", "number": "C-001"}))
        result = await client.push({"title": "PSA"}, change_type="request_for_change")
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["external_id"] == "CHG-001"

    @pytest.mark.asyncio
    async def test_push_auth_failure(self):
        client = TOPdeskClient(base_url="https://x.com", api_key="bad")
        _inject_mock(client, _json_response(401, {}))
        result = await client.push({"title": "PSA"})
        assert result.status == IntegrationStatus.FAILED

    def test_rate_limit_config(self):
        assert TOPdeskClient(base_url="https://x.com").rate_limit_per_second == 1.6


class TestLeanIXClient:
    def test_normalize_dict(self):
        client = LeanIXClient(base_url="https://eu.leanix.net")
        result = client.normalize(
            {
                "id": "LX-1",
                "displayName": "Sysmex",
                "type": "Application",
                "lifecycle": {"phase": "Active"},
            }
        )
        assert result["source_id"] == "LX-1"
        assert result["name"] == "Sysmex"
        assert result["status"] == "Active"

    def test_graphql_url(self):
        client = LeanIXClient(base_url="https://eu.leanix.net")
        assert "/graphql" in client._graphql_url()

    def test_auth_headers(self):
        client = LeanIXClient(base_url="https://eu.leanix.net", api_key="lx-key")
        assert client._headers()["Authorization"] == "Bearer lx-key"

    @pytest.mark.asyncio
    async def test_health_success(self):
        client = LeanIXClient(base_url="https://eu.leanix.net", api_key="test")
        _inject_mock(client, _json_response(200, {"data": {"factSheetCount": 42}}))
        result = await client.health()
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["application_count"] == 42

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        client = LeanIXClient(base_url="https://eu.leanix.net", api_key="test")
        _inject_mock(
            client,
            _json_response(
                200,
                {
                    "data": {
                        "factSheets": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "LX-1",
                                        "displayName": "Sysmex",
                                        "type": "Application",
                                        "lifecycle": {"phase": "Active"},
                                    }
                                }
                            ],
                            "totalCount": 1,
                        }
                    }
                },
            ),
        )
        result = await client.fetch("Sysmex")
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_fetch_auth_failure(self):
        client = LeanIXClient(base_url="https://eu.leanix.net", api_key="bad")
        _inject_mock(client, _json_response(401, {"error": "unauthorized"}))
        result = await client.fetch("test")
        assert result.status == IntegrationStatus.FAILED

    @pytest.mark.asyncio
    async def test_push_without_fact_sheet_id(self):
        client = LeanIXClient(base_url="https://eu.leanix.net", api_key="test")
        result = await client.push({"tag": "assessed"})
        assert result.status == IntegrationStatus.FAILED

    @pytest.mark.asyncio
    async def test_push_success(self):
        client = LeanIXClient(base_url="https://eu.leanix.net", api_key="test")
        _inject_mock(
            client,
            _json_response(
                200,
                {
                    "data": {
                        "updateFactSheet": {"factSheet": {"id": "LX-1", "displayName": "Sysmex"}}
                    }
                },
            ),
        )
        result = await client.push({"tag": "assessed"}, fact_sheet_id="LX-1")
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["external_id"] == "LX-1"

    def test_rate_limit_config(self):
        assert LeanIXClient(base_url="https://eu.leanix.net").rate_limit_per_second == 1.0


class TestGraphClient:
    def test_normalize_dict(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0")
        result = client.normalize(
            {
                "id": "D-1",
                "name": "policy.pdf",
                "file": {"mimeType": "application/pdf"},
                "webUrl": "https://sp.example.com/policy.pdf",
                "lastModifiedDateTime": "2026-04-01",
                "size": 1024,
            }
        )
        assert result["source_id"] == "D-1"
        assert result["name"] == "policy.pdf"

    def test_drive_url_with_site_id(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0", site_id="site-123")
        assert "site-123" in client._drive_url()
        assert "/drive" in client._drive_url()

    def test_drive_url_with_drive_id(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0", drive_id="drive-456")
        assert "drive-456" in client._drive_url()

    def test_drive_url_default(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0")
        assert "/me/drive" in client._drive_url()

    @pytest.mark.asyncio
    async def test_health_success(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0", api_key="test")
        _inject_mock(client, _json_response(200, {"displayName": "Test User"}))
        result = await client.health()
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["connected"] is True

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0", api_key="test")
        _inject_mock(
            client,
            _json_response(
                200,
                {
                    "value": [
                        {
                            "id": "1",
                            "name": "policy.pdf",
                            "file": {"mimeType": "application/pdf"},
                            "webUrl": "https://sp.example.com/policy.pdf",
                            "lastModifiedDateTime": "2026-04-01",
                            "size": 1024,
                        },
                        {
                            "id": "2",
                            "name": "NEN7510.pdf",
                            "file": {"mimeType": "application/pdf"},
                            "webUrl": "https://sp.example.com/NEN7510.pdf",
                            "lastModifiedDateTime": "2026-03-15",
                            "size": 2048,
                        },
                    ]
                },
            ),
        )
        result = await client.fetch("NEN 7510")
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_push_success(self):
        client = GraphClient(
            base_url="https://graph.microsoft.com/v1.0", api_key="test", drive_id="d-1"
        )
        _inject_mock(
            client,
            _json_response(
                201, {"id": "F-1", "webUrl": "https://sp.example.com/Assessments/assessment.md"}
            ),
        )
        result = await client.push(
            {"file_name": "assessment.md", "content": "# PSA"}, folder="Assessments"
        )
        assert result.status == IntegrationStatus.SUCCESS
        assert result.data["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_push_auth_failure(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0", api_key="bad")
        _inject_mock(client, _json_response(401, {"error": {"code": "InvalidAuthenticationToken"}}))
        result = await client.push({"file_name": "test.md", "content": "test"})
        assert result.status == IntegrationStatus.FAILED

    @pytest.mark.asyncio
    async def test_health_unavailable(self):
        client = GraphClient(base_url="https://graph.microsoft.com/v1.0")

        def conn_refused(req):
            raise httpx.ConnectError("Connection refused")

        client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(conn_refused))
        result = await client.health()
        assert result.status == IntegrationStatus.UNAVAILABLE

    def test_rate_limit_config(self):
        assert (
            GraphClient(base_url="https://graph.microsoft.com/v1.0").rate_limit_per_second == 30.0
        )
