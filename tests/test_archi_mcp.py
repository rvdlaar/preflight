"""
Tests for Archi MCP client, merger, and reader.

Live integration tests are marked with @pytest.mark.live_archi and
require Archi running with archi-mcp-server at localhost:18090.
Offline tests mock the HTTP transport.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from preflight.model.types import (
    ArchiMateElement,
    ArchiMateModel,
    ArchiMateRelationship,
    ElementType,
    Layer,
    RelationshipType,
    make_element_id,
)
from preflight.model.archi_client import ArchiMCPClient, MCPToolResult
from preflight.model.merger import MergeResult
from preflight.model.archi_reader import ArchiLandscape, landscape_to_context


class TestMCPToolResult:
    def test_text_extraction(self):
        r = MCPToolResult(
            success=True,
            content=[{"type": "text", "text": "hello"}],
        )
        assert r.text == "hello"

    def test_data_from_text(self):
        r = MCPToolResult(
            success=True,
            content=[{"type": "text", "text": '{"name": "test", "result": {"a": 1}}'}],
        )
        assert r.data == {"a": 1}

    def test_data_plain_json(self):
        r = MCPToolResult(
            success=True,
            content=[{"type": "text", "text": '{"items": [1, 2, 3]}'}],
        )
        assert r.data == {"items": [1, 2, 3]}

    def test_data_no_content(self):
        r = MCPToolResult(success=False, error="timeout")
        assert r.data is None

    def test_error_result(self):
        r = MCPToolResult(success=False, error="connection refused")
        assert r.text == ""
        assert r.data is None


class TestMergeResult:
    def test_totals(self):
        r = MergeResult(
            created_elements=3,
            reused_elements=2,
            flagged_elements=1,
            created_relationships=5,
            reused_relationships=1,
            skipped_relationships=0,
        )
        assert r.total_elements == 6
        assert r.total_relationships == 6


class TestArchiLandscape:
    def test_to_context(self):
        landscape = ArchiLandscape(
            applications=[
                {"name": "HIS", "id": "id1", "type": "ApplicationComponent"},
                {"name": "LIS", "id": "id2", "type": "ApplicationComponent"},
            ],
            business_functions=[
                {"name": "Laboratorium", "id": "id3"},
            ],
            interfaces=[
                {"name": "HL7 IF", "id": "id4", "type": "ApplicationInterface"},
            ],
            model_name="AI-BOK Referentiearchitectuur",
        )
        ctx = landscape_to_context(landscape)
        assert ctx["source"] == "archi-mcp"
        assert len(ctx["existingApps"]) == 2
        assert ctx["existingApps"][0]["name"] == "HIS"
        assert len(ctx["businessFunctions"]) == 1
        assert ctx["businessFunctions"][0]["name"] == "Laboratorium"
        assert len(ctx["relatedInterfaces"]) == 1
        assert ctx["model_name"] == "AI-BOK Referentiearchitectuur"

    def test_empty_landscape(self):
        landscape = ArchiLandscape()
        ctx = landscape_to_context(landscape)
        assert ctx["existingApps"] == []
        assert ctx["source"] == "archi-mcp"


class TestMCPClientOffline:
    def test_client_init(self):
        client = ArchiMCPClient(base_url="http://localhost:9999/mcp")
        assert client.base_url == "http://localhost:9999/mcp"
        assert client._session_id is None

    def test_next_id_increments(self):
        client = ArchiMCPClient()
        assert client._next_id() == 1
        assert client._next_id() == 2
        assert client._next_id() == 3


# -----------------------------------------------------------------------
# Live integration tests — require Archi + MCP server running
# -----------------------------------------------------------------------

LIVE_ARCHI = False


@pytest.mark.skipif(not LIVE_ARCHI, reason="Set LIVE_ARCHI=True to run live Archi tests")
class TestMCPClientLive:
    @pytest.fixture
    async def client(self):
        async with ArchiMCPClient() as c:
            yield c

    @pytest.mark.asyncio
    async def test_get_model_info(self, client):
        info = await client.get_model_info()
        assert "elementCount" in info
        assert int(info["elementCount"]) > 0

    @pytest.mark.asyncio
    async def test_search_elements_by_type(self, client):
        results = await client.search_elements(type="ApplicationComponent", limit=5)
        assert isinstance(results, list)
        assert len(results) > 0
        assert results[0].get("type") == "ApplicationComponent"

    @pytest.mark.asyncio
    async def test_search_elements_by_query(self, client):
        results = await client.search_elements(query="Service", limit=10)
        assert isinstance(results, list)
        for r in results:
            assert "Service" in r.get("name", "")

    @pytest.mark.asyncio
    async def test_get_relationships(self, client):
        rels = await client.get_relationships(limit=5)
        assert isinstance(rels, list)

    @pytest.mark.asyncio
    async def test_is_alive(self, client):
        assert await client.is_alive() is True

    @pytest.mark.asyncio
    async def test_create_and_delete_element(self, client):
        result = await client.create_element(
            type="BusinessActor",
            name="Test Preflight Actor",
            documentation="Created by Preflight test",
        )
        assert result.success
        data = result.data or {}
        elem_id = data.get("id", data.get("elementId", ""))
        assert elem_id

        del_result = await client.delete_element(elem_id)
        assert del_result.success

    @pytest.mark.asyncio
    async def test_approval_mode(self, client):
        result = await client.set_approval_mode(True)
        assert result.success
        result2 = await client.set_approval_mode(False)
        assert result2.success
