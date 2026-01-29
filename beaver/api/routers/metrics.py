from typing import Any

from fastapi import APIRouter

from beaver.api.auth import Auth
from beaver.api.deps import DBSession
from beaver.core.exceptions import AuthorizationError
from beaver.services.metrics import get_metrics

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/usage")
async def get_usage(auth: Auth, session: DBSession, days: int = 30) -> dict[str, Any]:
    svc = get_metrics()
    return await svc.get_user_stats(session, auth.user_id, days)


@router.get("/system")
async def get_system(auth: Auth, session: DBSession, days: int = 30) -> dict[str, Any]:
    if not auth.is_admin:
        raise AuthorizationError("Admin access required")
    svc = get_metrics()
    return await svc.get_system_stats(session, days)


@router.get("/requests")
async def get_requests(
    auth: Auth,
    session: DBSession,
    limit: int = 100,
) -> list[dict[str, Any]]:
    svc = get_metrics()
    uid = None if auth.is_admin else auth.user_id
    return await svc.get_recent_requests(session, uid, min(limit, 1000))
