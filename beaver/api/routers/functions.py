from fastapi import APIRouter

from beaver.api.auth import Auth
from beaver.api.deps import DBSession
from beaver.core.exceptions import NotFoundError
from beaver.core.schemas import (
    FunctionCreate,
    FunctionExecuteRequest,
    FunctionExecuteResponse,
    FunctionInfo,
)
from beaver.services.functions import get_functions

router = APIRouter(prefix="/functions", tags=["Functions"])


@router.get("", response_model=list[FunctionInfo])
async def list_functions(auth: Auth, session: DBSession):
    auth.require_scope("functions")
    svc = get_functions()
    funcs = await svc.list(session, auth.user_id)
    return [
        FunctionInfo(
            id=str(f.id),
            name=f.name,
            description=f.description,
            parameters=f.parameters_schema,
            endpoint=f.endpoint,
            is_builtin=f.is_builtin,
            is_active=f.is_active,
        )
        for f in funcs
    ]


@router.post("", response_model=FunctionInfo)
async def create_function(request: FunctionCreate, auth: Auth, session: DBSession):
    auth.require_scope("functions")
    svc = get_functions()
    f = await svc.create(
        session,
        auth.user_id,
        request.name,
        request.description,
        request.parameters,
        request.endpoint,
    )
    return FunctionInfo(
        id=str(f.id),
        name=f.name,
        description=f.description,
        parameters=f.parameters_schema,
        endpoint=f.endpoint,
        is_builtin=f.is_builtin,
        is_active=f.is_active,
    )


@router.get("/{name}", response_model=FunctionInfo)
async def get_function(name: str, auth: Auth, session: DBSession):
    auth.require_scope("functions")
    svc = get_functions()
    f = await svc.get(session, name, auth.user_id)
    if not f:
        raise NotFoundError("Function", name)
    return FunctionInfo(
        id=str(f.id),
        name=f.name,
        description=f.description,
        parameters=f.parameters_schema,
        endpoint=f.endpoint,
        is_builtin=f.is_builtin,
        is_active=f.is_active,
    )


@router.post("/{name}/execute", response_model=FunctionExecuteResponse)
async def execute_function(
    name: str,
    request: FunctionExecuteRequest,
    auth: Auth,
    session: DBSession,
):
    auth.require_scope("functions")
    svc = get_functions()
    result = await svc.execute(session, name, request.arguments, auth.user_id)
    err = result.pop("error", None) if isinstance(result, dict) else None
    return FunctionExecuteResponse(result=result, error=err)
