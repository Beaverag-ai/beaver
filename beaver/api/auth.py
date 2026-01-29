import secrets
import hashlib
from typing import Annotated
from datetime import datetime, timedelta, UTC

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from beaver.config import get_settings
from beaver.db.models import APIKey, User
from beaver.db.session import get_session
from beaver.core.exceptions import AuthenticationError, AuthorizationError

cfg = get_settings()


def generate_api_key() -> str:
    return cfg.api_key_prefix + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_key_prefix(key: str) -> str:
    return key[: len(cfg.api_key_prefix) + 4] + "..."


async def create_api_key(
    session: AsyncSession,
    user_id: str,
    name: str,
    scopes: str = "chat,knowledge,functions",
    expires_in_days: int | None = None,
) -> tuple[str, APIKey]:
    raw = generate_api_key()
    expires = (
        datetime.now(UTC) + timedelta(days=expires_in_days)
        if expires_in_days
        else None
    )

    key = APIKey(
        user_id=user_id,
        key_hash=hash_api_key(raw),
        key_prefix=get_key_prefix(raw),
        name=name,
        scopes=scopes,
        expires_at=expires,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return raw, key


async def verify_api_key(session: AsyncSession, key: str) -> tuple[User, APIKey]:
    h = hash_api_key(key)
    result = await session.execute(
        select(APIKey).where(APIKey.key_hash == h, APIKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise AuthenticationError("Invalid API key")
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        raise AuthenticationError("API key has expired")

    result = await session.execute(
        select(User).where(User.id == api_key.user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User account is inactive")

    return user, api_key


def extract_bearer_token(auth_header: str | None) -> str:
    if not auth_header:
        raise AuthenticationError("Missing Authorization header")
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header format")
    return parts[1]


class AuthContext:
    def __init__(self, user: User, api_key: APIKey):
        self.user = user
        self.api_key = api_key
        self.user_id = str(user.id)
        self.scopes = set(api_key.scopes.split(","))

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise AuthorizationError(f"Missing required scope: {scope}")

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"


async def get_auth_context(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    token = extract_bearer_token(authorization)
    user, api_key = await verify_api_key(session, token)
    return AuthContext(user, api_key)


async def get_optional_auth_context(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> AuthContext | None:
    if not authorization:
        return None
    try:
        return AuthContext(
            *await verify_api_key(session, extract_bearer_token(authorization))
        )
    except AuthenticationError:
        return None


Auth = Annotated[AuthContext, Depends(get_auth_context)]
OptionalAuth = Annotated[AuthContext | None, Depends(get_optional_auth_context)]
