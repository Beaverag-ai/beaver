from fastapi import APIRouter
from sqlalchemy import select

from beaver.api.auth import Auth, create_api_key
from beaver.api.deps import DBSession
from beaver.db.models import APIKey, User
from beaver.core.exceptions import NotFoundError
from beaver.core.schemas import (
    APIKeyCreate,
    APIKeyInfo,
    APIKeyResponse,
    UserInfo,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=UserInfo)
async def get_me(auth: Auth):
    u = auth.user
    return UserInfo(
        id=str(u.id),
        email=u.email,
        name=u.name,
        role=u.role,
        created_at=u.created_at,
    )


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_key(request: APIKeyCreate, auth: Auth, session: DBSession):
    raw, key = await create_api_key(
        session,
        auth.user_id,
        request.name,
        request.scopes,
        request.expires_in_days,
    )
    return APIKeyResponse(
        id=str(key.id),
        key=raw,
        key_prefix=key.key_prefix,
        name=key.name,
        scopes=key.scopes,
        created_at=key.created_at,
        expires_at=key.expires_at,
    )


@router.get("/api-keys", response_model=list[APIKeyInfo])
async def list_keys(auth: Auth, session: DBSession):
    result = await session.execute(
        select(APIKey)
        .where(APIKey.user_id == auth.user_id, APIKey.is_active == True)
        .order_by(APIKey.created_at.desc())
    )
    return [
        APIKeyInfo(
            id=str(k.id),
            key_prefix=k.key_prefix,
            name=k.name,
            scopes=k.scopes,
            created_at=k.created_at,
            expires_at=k.expires_at,
            is_active=k.is_active,
        )
        for k in result.scalars().all()
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_key(key_id: str, auth: Auth, session: DBSession):
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == auth.user_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise NotFoundError("API key", key_id)

    key.is_active = False
    await session.commit()
    return {"revoked": True, "id": key_id}


@router.get("/users", response_model=list[UserInfo])
async def list_users(auth: Auth, session: DBSession):
    if not auth.is_admin:
        raise NotFoundError("Endpoint")

    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return [
        UserInfo(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            created_at=u.created_at,
        )
        for u in result.scalars().all()
    ]
