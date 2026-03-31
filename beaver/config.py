from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # server
    api_host: str = "0.0.0.0"
    api_port: int = 8741
    api_workers: int = 1
    debug: bool = False

    # postgres
    database_url: str = "postgresql+asyncpg://beaver:beaver@localhost:5491/beaver"

    # vector store (pgvector — uses the same database_url as postgres)
    vector_collection: str = "beaver_knowledge"

    # llm backend
    sglang_url: str = "http://localhost:30091"
    default_model: str = "beaver-default"

    # embeddings
    ollama_url: str = "http://localhost:11491"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768  # nomic-embed-text dimension

    # perplexity for web search
    perplexity_api_key: str = ""

    # storage
    uploads_dir: Path = Path("./uploads")

    # auth
    api_key_prefix: str = "bvr_"
    token_expire_days: int = 365

    # rag params
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5

    # limits
    max_upload_mb: int = 100
    max_context_tokens: int = 8192


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    return s
