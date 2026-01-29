from uuid import uuid4
from datetime import datetime, UTC

from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid4] = mapped_column(UUID, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid4] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    key_prefix: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[str] = mapped_column(String(255), default="chat,knowledge,functions")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes.split(",")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid4] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    filepath: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Function(Base):
    __tablename__ = "functions"

    id: Mapped[uuid4] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4 | None] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    parameters_schema: Mapped[dict] = mapped_column(JSONB)
    endpoint: Mapped[str | None] = mapped_column(String(1024))
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid4] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    transport: Mapped[str] = mapped_column(String(50))  # stdio, sse, websocket
    command: Mapped[str | None] = mapped_column(String(1024))
    args: Mapped[list | None] = mapped_column(JSONB)
    env: Mapped[dict | None] = mapped_column(JSONB)
    url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[uuid4] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(UUID, index=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10), default="POST")
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
