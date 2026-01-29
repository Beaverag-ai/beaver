import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from beaver.db.models import MCPServer
from beaver.mcp.client import MCPClient

log = logging.getLogger(__name__)


class MCPManager:
    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._lock = asyncio.Lock()

    async def add_server(
        self,
        session: AsyncSession,
        user_id: str,
        name: str,
        transport: str,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        url: str | None = None,
    ) -> MCPServer:
        srv = MCPServer(
            user_id=user_id,
            name=name,
            transport=transport,
            command=command,
            args=args,
            env=env,
            url=url,
        )
        session.add(srv)
        await session.commit()
        await session.refresh(srv)

        # try to connect immediately
        await self.connect_server(srv)
        return srv

    async def connect_server(self, server: MCPServer) -> MCPClient:
        async with self._lock:
            sid = str(server.id)
            if sid in self._clients and self._clients[sid].is_connected:
                return self._clients[sid]

            client = MCPClient(
                server_id=sid,
                name=server.name,
                transport=server.transport,
                command=server.command,
                args=server.args,
                env=server.env,
                url=server.url,
            )
            await client.connect()
            self._clients[sid] = client
            return client

    async def disconnect_server(self, server_id: str) -> None:
        async with self._lock:
            if server_id in self._clients:
                await self._clients[server_id].disconnect()
                del self._clients[server_id]

    async def get_client(self, server_id: str) -> MCPClient | None:
        return self._clients.get(server_id)

    async def ensure_connected(
        self,
        session: AsyncSession,
        server_id: str,
    ) -> MCPClient | None:
        client = self._clients.get(server_id)
        if client and client.is_connected:
            return client

        # try to connect
        result = await session.execute(
            select(MCPServer).where(
                MCPServer.id == server_id,
                MCPServer.is_active == True,
            )
        )
        srv = result.scalar_one_or_none()
        if not srv:
            return None

        return await self.connect_server(srv)

    async def list_servers(self, session: AsyncSession, user_id: str) -> list[MCPServer]:
        result = await session.execute(
            select(MCPServer)
            .where(MCPServer.user_id == user_id, MCPServer.is_active == True)
            .order_by(MCPServer.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_server(
        self,
        session: AsyncSession,
        server_id: str,
        user_id: str,
    ) -> bool:
        await self.disconnect_server(server_id)

        result = await session.execute(
            select(MCPServer).where(
                MCPServer.id == server_id,
                MCPServer.user_id == user_id,
            )
        )
        srv = result.scalar_one_or_none()
        if srv:
            srv.is_active = False
            await session.commit()
            return True
        return False

    async def get_tools_from_server(
        self,
        session: AsyncSession,
        server_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        client = await self.ensure_connected(session, server_id)
        return client.get_tools() if client else []

    async def get_all_tools(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> list[dict[str, Any]]:
        servers = await self.list_servers(session, user_id)
        tools = []

        for srv in servers:
            client = await self.ensure_connected(session, str(srv.id))
            if client:
                for t in client.get_tools():
                    tools.append({
                        **t,
                        "server_id": str(srv.id),
                        "server_name": srv.name,
                    })

        return tools

    async def call_tool(
        self,
        session: AsyncSession,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        client = await self.ensure_connected(session, server_id)
        if not client:
            raise ValueError(f"Server {server_id} not found")
        return await client.call_tool(tool_name, arguments)

    async def close_all(self) -> None:
        async with self._lock:
            for client in self._clients.values():
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self._clients.clear()


_mgr: MCPManager | None = None


def get_mcp_manager() -> MCPManager:
    global _mgr
    if not _mgr:
        _mgr = MCPManager()
    return _mgr


async def close_mcp_manager() -> None:
    global _mgr
    if _mgr:
        await _mgr.close_all()
        _mgr = None
