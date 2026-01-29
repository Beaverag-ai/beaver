import logging
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client

log = logging.getLogger(__name__)


class MCPClient:
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
        read, write = await stdio_client(params).__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def _connect_sse(self) -> None:
        if not self.url:
            raise ValueError("URL required for SSE transport")

        read, write = await sse_client(self.url).__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def _discover_tools(self) -> None:
        if not self._session:
            return

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

    def get_tools(self) -> list[dict[str, Any]]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if not self._session:
            raise RuntimeError("Not connected")
        result = await self._session.call_tool(name, arguments)
        return result.content

    async def disconnect(self) -> None:
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None

        self._connected = False
        self._tools = []
        log.info(f"Disconnected from: {self.name}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
