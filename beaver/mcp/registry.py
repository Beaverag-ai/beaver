from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from beaver.mcp.manager import get_mcp_manager


class MCPRegistry:
    def __init__(self):
        self._mgr = get_mcp_manager()

    async def discover_tools(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> list[dict[str, Any]]:
        return await self._mgr.get_all_tools(session, user_id)

    async def get_tools_for_server(
        self,
        session: AsyncSession,
        server_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        return await self._mgr.get_tools_from_server(session, server_id, user_id)

    async def call_tool(
        self,
        session: AsyncSession,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        return await self._mgr.call_tool(session, server_id, tool_name, arguments)

    def to_openai_format(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": f"mcp_{t.get('server_id', 'unknown')}_{t['name']}",
                    "description": t.get("description", ""),
                    "parameters": t.get(
                        "input_schema",
                        {"type": "object", "properties": {}},
                    ),
                },
            }
            for t in tools
        ]

    def parse_tool_call(self, name: str) -> tuple[str, str] | None:
        if not name.startswith("mcp_"):
            return None
        parts = name[4:].split("_", 1)
        return (parts[0], parts[1]) if len(parts) == 2 else None


_reg: MCPRegistry | None = None


def get_mcp_registry() -> MCPRegistry:
    global _reg
    if not _reg:
        _reg = MCPRegistry()
    return _reg
