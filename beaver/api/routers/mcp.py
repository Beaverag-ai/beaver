from fastapi import APIRouter

from beaver.api.auth import Auth
from beaver.api.deps import DBSession
from beaver.core.exceptions import NotFoundError
from beaver.core.schemas import (
    MCPServerCreate,
    MCPServerInfo,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolInfo,
)
from beaver.mcp.manager import get_mcp_manager
from beaver.mcp.registry import get_mcp_registry

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.post("/servers", response_model=MCPServerInfo)
async def create_server(request: MCPServerCreate, auth: Auth, session: DBSession):
    auth.require_scope("functions")
    mgr = get_mcp_manager()
    srv = await mgr.add_server(
        session,
        auth.user_id,
        request.name,
        request.transport,
        request.command,
        request.args,
        request.env,
        request.url,
    )
    return MCPServerInfo(
        id=str(srv.id),
        name=srv.name,
        transport=srv.transport,
        command=srv.command,
        url=srv.url,
        is_active=srv.is_active,
        created_at=srv.created_at,
    )


@router.get("/servers", response_model=list[MCPServerInfo])
async def list_servers(auth: Auth, session: DBSession):
    auth.require_scope("functions")
    mgr = get_mcp_manager()
    servers = await mgr.list_servers(session, auth.user_id)
    return [
        MCPServerInfo(
            id=str(s.id),
            name=s.name,
            transport=s.transport,
            command=s.command,
            url=s.url,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in servers
    ]


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str, auth: Auth, session: DBSession):
    auth.require_scope("functions")
    mgr = get_mcp_manager()
    if not await mgr.delete_server(session, server_id, auth.user_id):
        raise NotFoundError("MCP server", server_id)
    return {"deleted": True, "id": server_id}


@router.get("/servers/{server_id}/tools", response_model=list[MCPToolInfo])
async def list_server_tools(server_id: str, auth: Auth, session: DBSession):
    auth.require_scope("functions")
    reg = get_mcp_registry()
    tools = await reg.get_tools_for_server(session, server_id, auth.user_id)
    if not tools:
        raise NotFoundError("MCP server", server_id)

    # get server name
    mgr = get_mcp_manager()
    servers = await mgr.list_servers(session, auth.user_id)
    name = next((s.name for s in servers if str(s.id) == server_id), "unknown")

    return [
        MCPToolInfo(
            name=t["name"],
            description=t.get("description"),
            input_schema=t.get("input_schema"),
            server_id=server_id,
            server_name=name,
        )
        for t in tools
    ]


@router.get("/tools", response_model=list[MCPToolInfo])
async def list_all_tools(auth: Auth, session: DBSession):
    auth.require_scope("functions")
    reg = get_mcp_registry()
    tools = await reg.discover_tools(session, auth.user_id)
    return [
        MCPToolInfo(
            name=t["name"],
            description=t.get("description"),
            input_schema=t.get("input_schema"),
            server_id=t.get("server_id", ""),
            server_name=t.get("server_name", "unknown"),
        )
        for t in tools
    ]


@router.post("/tools/{tool_name}/call", response_model=MCPToolCallResponse)
async def call_tool(
    tool_name: str,
    request: MCPToolCallRequest,
    auth: Auth,
    session: DBSession,
    server_id: str | None = None,
):
    auth.require_scope("functions")
    reg = get_mcp_registry()

    # find server if not specified
    if not server_id:
        tools = await reg.discover_tools(session, auth.user_id)
        match = [t for t in tools if t["name"] == tool_name]
        if not match:
            raise NotFoundError("MCP tool", tool_name)
        server_id = match[0]["server_id"]

    try:
        result = await reg.call_tool(session, server_id, tool_name, request.arguments)
        return MCPToolCallResponse(result=result)
    except Exception as e:
        return MCPToolCallResponse(result=None, error=str(e))
