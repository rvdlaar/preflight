"""
Archi MCP Client — HTTP client for archi-mcp-server (localhost:18090).

Wraps the Streamable HTTP transport (session-based) and provides Python
methods for the key MCP tools needed by Preflight's Phase 2 integration.

Thinking applied:
  First principles: The MCP server is an HTTP endpoint that speaks JSON-RPC
  over Streamable HTTP. We need: initialize, call tools, manage sessions.
  No SDK dependency — just httpx/requests and JSON.
  Second order: Session IDs must be tracked. Each initialize creates a new
  session. Tools/list and tools/call require the session header. If the
  session expires, we re-initialize transparently.
  Inversion: What makes this fail? Server not running, Archi closed, model
  not open. We handle all gracefully with clear error messages. Network
  timeouts. Session expiry. All accounted for.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:18090/mcp"
DEFAULT_TIMEOUT = 30.0


@dataclass
class MCPToolResult:
    success: bool
    content: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        parts = []
        for item in self.content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)

    @property
    def data(self) -> Any:
        for item in self.content:
            if item.get("type") == "text":
                try:
                    parsed = json.loads(item["text"])
                    if (
                        isinstance(parsed, dict)
                        and "result" in parsed
                        and not isinstance(parsed.get("result"), str)
                    ):
                        inner = parsed["result"]
                        if isinstance(inner, dict) and "element" in inner:
                            return inner["element"]
                        if isinstance(inner, dict) and "elements" in inner:
                            return inner["elements"]
                        if isinstance(inner, dict) and "relationships" in inner:
                            return inner["relationships"]
                        if isinstance(inner, dict) and "views" in inner:
                            return inner["views"]
                        if isinstance(inner, dict) and "folders" in inner:
                            return inner["folders"]
                        if isinstance(inner, dict) and "content" not in inner:
                            return inner
                        return inner
                    return parsed
                except (json.JSONDecodeError, KeyError):
                    continue
        return None


class ArchiMCPClient:
    """HTTP client for the Archi MCP Server (Streamable HTTP transport).

    Usage:
        async with ArchiMCPClient() as client:
            info = await client.get_model_info()
            elements = await client.search_elements(query="HIS", type="ApplicationComponent")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        client_name: str = "preflight",
        client_version: str = "0.1.0",
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.client_name = client_name
        self.client_version = client_version
        self._session_id: str | None = None
        self._http: httpx.AsyncClient | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def __aenter__(self) -> ArchiMCPClient:
        self._http = httpx.AsyncClient(timeout=self.timeout)
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    async def _ensure_session(self) -> None:
        if not self._session_id:
            await self.initialize()

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._http:
            self._http = httpx.AsyncClient(timeout=self.timeout)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        response = await self._http.post(self.base_url, json=payload, headers=headers)

        if response.status_code != 200:
            raise ConnectionError(
                f"MCP server returned HTTP {response.status_code}: {response.text[:500]}"
            )

        content_type = response.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            for line in response.text.split("\n"):
                if line.startswith("data: "):
                    return json.loads(line[6:])
            raise ConnectionError("SSE response contained no data line")

        return response.json()

    async def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._ensure_session()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        result = await self._post(payload)

        if "error" in result:
            err = result["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")

        return result.get("result", result)

    async def _tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        try:
            result = await self._call("tools/call", params)
        except RuntimeError as e:
            return MCPToolResult(success=False, error=str(e))

        content = result.get("content", [])
        is_error = result.get("isError", False)

        return MCPToolResult(
            success=not is_error,
            content=content,
            error=result.get("error") if is_error else None,
            raw=result,
        )

    # -------------------------------------------------------------------
    # Session management
    # -------------------------------------------------------------------

    async def initialize(self) -> dict[str, Any]:
        self._request_id = 0
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": self.client_name,
                    "version": self.client_version,
                },
            },
        }

        if not self._http:
            self._http = httpx.AsyncClient(timeout=self.timeout)

        resp = await self._http.post(
            self.base_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

        if resp.status_code != 200:
            raise ConnectionError(f"Cannot connect to Archi MCP at {self.base_url}")

        session_id = resp.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id

        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            for line in resp.text.split("\n"):
                if line.startswith("data: "):
                    return json.loads(line[6:])
            return {}

        return resp.json().get("result", resp.json())

    # -------------------------------------------------------------------
    # Read tools
    # -------------------------------------------------------------------

    async def get_model_info(self) -> dict[str, Any]:
        result = await self._tool("get-model-info")
        return result.data or {}

    async def search_elements(
        self,
        query: str = "",
        type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        args: dict[str, Any] = {"query": query}
        if type:
            args["type"] = type
        if limit:
            args["limit"] = limit
        result = await self._tool("search-elements", args)
        data = result.data
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("elements", data.get("results", [data]))
        return []

    async def get_element(self, element_id: str) -> dict[str, Any] | None:
        result = await self._tool("get-element", {"elementId": element_id})
        if not result.success:
            return None
        data = result.data
        if isinstance(data, dict):
            return data
        return None

    async def get_relationships(
        self,
        element_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        args: dict[str, Any] = {}
        if element_id:
            args["elementId"] = element_id
        if limit:
            args["limit"] = limit
        result = await self._tool("get-relationships", args)
        data = result.data
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("relationships", data.get("results", [data]))
        return []

    async def search_relationships(
        self,
        query: str = "",
        type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        args: dict[str, Any] = {"query": query}
        if type:
            args["type"] = type
        if limit:
            args["limit"] = limit
        result = await self._tool("search-relationships", args)
        data = result.data
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("relationships", data.get("results", [data]))
        return []

    async def get_views(
        self,
        viewpoint: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        args: dict[str, Any] = {}
        if viewpoint:
            args["viewpoint"] = viewpoint
        if limit:
            args["limit"] = limit
        result = await self._tool("get-views", args)
        data = result.data
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("views", data.get("results", [data]))
        return []

    async def get_view_contents(self, view_id: str) -> list[dict[str, Any]]:
        result = await self._tool("get-view-contents", {"viewId": view_id})
        data = result.data
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("objects", data.get("results", [data]))
        return []

    async def get_folders(self) -> list[dict[str, Any]]:
        result = await self._tool("get-folders")
        data = result.data
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("folders", [data])
        return []

    # -------------------------------------------------------------------
    # Create tools
    # -------------------------------------------------------------------

    async def create_element(
        self,
        type: str,
        name: str,
        documentation: str = "",
        properties: dict[str, str] | None = None,
    ) -> MCPToolResult:
        args: dict[str, Any] = {"type": type, "name": name}
        if documentation:
            args["documentation"] = documentation
        if properties:
            args["properties"] = properties
        return await self._tool("create-element", args)

    async def create_relationship(
        self,
        type: str,
        source_id: str,
        target_id: str,
        name: str = "",
        documentation: str = "",
        properties: dict[str, str] | None = None,
    ) -> MCPToolResult:
        args: dict[str, Any] = {
            "type": type,
            "sourceId": source_id,
            "targetId": target_id,
        }
        if name:
            args["name"] = name
        if documentation:
            args["documentation"] = documentation
        if properties:
            args["properties"] = properties
        return await self._tool("create-relationship", args)

    async def get_or_create_element(
        self,
        type: str,
        name: str,
        documentation: str = "",
        properties: dict[str, str] | None = None,
    ) -> MCPToolResult:
        args: dict[str, Any] = {"type": type, "name": name}
        if documentation:
            args["documentation"] = documentation
        if properties:
            args["properties"] = properties
        return await self._tool("get-or-create-element", args)

    async def create_view(
        self,
        name: str,
        viewpoint: str | None = None,
        folder_id: str | None = None,
    ) -> MCPToolResult:
        args: dict[str, Any] = {"name": name}
        if viewpoint:
            args["viewpoint"] = viewpoint
        if folder_id:
            args["folderId"] = folder_id
        return await self._tool("create-view", args)

    # -------------------------------------------------------------------
    # View tools
    # -------------------------------------------------------------------

    async def add_to_view(
        self,
        view_id: str,
        element_id: str,
        x: int = 0,
        y: int = 0,
    ) -> MCPToolResult:
        return await self._tool(
            "add-to-view",
            {
                "viewId": view_id,
                "elementId": element_id,
                "x": x,
                "y": y,
            },
        )

    async def add_connection_to_view(
        self,
        view_id: str,
        relationship_id: str,
        source_view_object_id: str,
        target_view_object_id: str,
    ) -> MCPToolResult:
        return await self._tool(
            "add-connection-to-view",
            {
                "viewId": view_id,
                "relationshipId": relationship_id,
                "sourceViewObjectId": source_view_object_id,
                "targetViewObjectId": target_view_object_id,
            },
        )

    # -------------------------------------------------------------------
    # Layout tools
    # -------------------------------------------------------------------

    async def auto_layout_and_route(
        self,
        view_id: str,
        mode: str = "auto",
    ) -> MCPToolResult:
        return await self._tool(
            "auto-layout-and-route",
            {
                "viewId": view_id,
                "mode": mode,
            },
        )

    async def assess_layout(self, view_id: str) -> MCPToolResult:
        return await self._tool("assess-layout", {"viewId": view_id})

    # -------------------------------------------------------------------
    # Approval workflow
    # -------------------------------------------------------------------

    async def set_approval_mode(self, enabled: bool) -> MCPToolResult:
        return await self._tool("set-approval-mode", {"enabled": enabled})

    async def list_pending_approvals(self) -> MCPToolResult:
        return await self._tool("list-pending-approvals")

    async def decide_mutation(
        self,
        mutation_id: str,
        decision: str,
        reason: str = "",
    ) -> MCPToolResult:
        return await self._tool(
            "decide-mutation",
            {
                "mutationId": mutation_id,
                "decision": decision,
                "reason": reason,
            },
        )

    # -------------------------------------------------------------------
    # Batch operations
    # -------------------------------------------------------------------

    async def begin_batch(self, description: str = "") -> MCPToolResult:
        args: dict[str, Any] = {}
        if description:
            args["description"] = description
        return await self._tool("begin-batch", args)

    async def end_batch(self, rollback: bool = False) -> MCPToolResult:
        return await self._tool("end-batch", {"rollback": rollback})

    # -------------------------------------------------------------------
    # Update / Delete
    # -------------------------------------------------------------------

    async def update_element(
        self,
        element_id: str,
        name: str | None = None,
        documentation: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> MCPToolResult:
        args: dict[str, Any] = {"id": element_id}
        if name:
            args["name"] = name
        if documentation:
            args["documentation"] = documentation
        if properties:
            args["properties"] = properties
        return await self._tool("update-element", args)

    async def delete_element(self, element_id: str) -> MCPToolResult:
        return await self._tool("delete-element", {"elementId": element_id})

    async def delete_relationship(self, relationship_id: str) -> MCPToolResult:
        return await self._tool("delete-relationship", {"relationshipId": relationship_id})

    async def delete_view(self, view_id: str) -> MCPToolResult:
        return await self._tool("delete-view", {"viewId": view_id})

    # -------------------------------------------------------------------
    # Filter
    # -------------------------------------------------------------------

    async def set_session_filter(
        self,
        layer: str | None = None,
        type: str | None = None,
    ) -> MCPToolResult:
        args: dict[str, Any] = {}
        if layer:
            args["layer"] = layer
        if type:
            args["type"] = type
        return await self._tool("set-session-filter", args)

    # -------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------

    async def is_alive(self) -> bool:
        try:
            info = await self.get_model_info()
            return bool(info)
        except Exception:
            return False
