from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client

log = logging.getLogger(__name__)


class MCPClient:
    """MCP client that connects via stdio or SSE transport."""

    def __init__(
        self,
        server_id: str,
        name: str,
        transport: str,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        url: str | None = None,
    ):
        self.server_id = server_id
        self.name = name
        self.transport = transport
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.url = url
        self._session: ClientSession | None = None
        self._tools: list[dict[str, Any]] = []
        self._connected = False
        self._transport_cm = None
        self._session_cm = None
        # For HTTP bridge-based connections
        self._http_client: httpx.AsyncClient | None = None
        self._http_base_url: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if self._connected:
            return

        try:
            if self.transport == "stdio":
                await self._connect_stdio()
            elif self.transport == "sse":
                await self._connect_sse()
            else:
                raise ValueError(f"Unsupported transport: {self.transport}")

            await self._discover_tools()
            self._connected = True
            log.info(f"Connected to MCP server: {self.name}")
        except Exception as e:
            log.error(f"Failed to connect to {self.name}: {e}")
            raise

    async def _connect_stdio(self) -> None:
        if not self.command:
            raise ValueError("Command required for stdio transport")

        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env or None,
        )
        self._transport_cm = stdio_client(params)
        read, write = await self._transport_cm.__aenter__()
        self._session = ClientSession(read, write)
        self._session_cm = self._session
        await self._session_cm.__aenter__()
        await self._session.initialize()

    async def _connect_sse(self) -> None:
        if not self.url:
            raise ValueError("URL required for SSE transport")

        # Derive base URL from SSE URL (e.g. http://host:3001/sse -> http://host:3001)
        base_url = self.url.rsplit("/", 1)[0]
        self._http_base_url = base_url
        self._http_client = httpx.AsyncClient(timeout=60)

        # Test connectivity and initialize via HTTP POST
        init_request = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "beaver", "version": "1.0"},
            },
        }
        resp = await self._http_client.post(
            f"{base_url}/message", json=init_request
        )
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise RuntimeError(f"MCP initialize failed: {result['error']}")
        log.info(f"MCP initialized: {result.get('result', {}).get('serverInfo', {})}")

    async def _discover_tools(self) -> None:
        if self._http_client and self._http_base_url:
            await self._discover_tools_http()
        elif self._session:
            await self._discover_tools_session()

    async def _discover_tools_session(self) -> None:
        try:
            result = await self._session.list_tools()
            self._tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": getattr(t, "inputSchema", None),
                }
                for t in result.tools
            ]
            log.info(f"Discovered {len(self._tools)} tools from {self.name}")
        except Exception as e:
            log.error(f"Failed to discover tools: {e}")
            self._tools = []

    async def _discover_tools_http(self) -> None:
        try:
            request = {
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "method": "tools/list",
                "params": {},
            }
            resp = await self._http_client.post(
                f"{self._http_base_url}/message", json=request
            )
            resp.raise_for_status()
            data = resp.json()
            tools = data.get("result", {}).get("tools", [])
            self._tools = [
                {
                    "name": t["name"],
                    "description": t.get("description"),
                    "input_schema": t.get("inputSchema"),
                }
                for t in tools
            ]
            log.info(f"Discovered {len(self._tools)} tools from {self.name}")
        except Exception as e:
            log.error(f"Failed to discover tools via HTTP: {e}")
            self._tools = []

    def get_tools(self) -> list[dict[str, Any]]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._http_client and self._http_base_url:
            return await self._call_tool_http(name, arguments)
        if not self._session:
            raise RuntimeError("Not connected")
        result = await self._session.call_tool(name, arguments)
        return result.content

    async def _call_tool_http(self, name: str, arguments: dict[str, Any]) -> Any:
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        resp = await self._http_client.post(
            f"{self._http_base_url}/message", json=request
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data.get("result", {}).get("content", [])

    async def disconnect(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self._http_base_url = None

        if self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_cm = None

        if self._transport_cm:
            try:
                await self._transport_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._transport_cm = None

        self._session = None
        self._connected = False
        self._tools = []
        log.info(f"Disconnected from: {self.name}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
