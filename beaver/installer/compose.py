"""Generate docker-compose.yml and .env for a Beaver installation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from beaver.installer.catalog import EmbeddingModel, MCP, Model, VectorStore


@dataclass
class InstallConfig:
    model: Model | None = None
    mcps: list[MCP] = field(default_factory=list)
    vector_store: VectorStore | None = None
    embedding: EmbeddingModel | None = None
    # MCP credentials (keyed by mcp name)
    mcp_env: dict[str, dict[str, str]] = field(default_factory=dict)
    output_dir: Path = field(default_factory=lambda: Path.cwd())


def generate_compose(cfg: InstallConfig) -> dict:
    """Build a docker-compose dict from install config."""
    services: dict = {}
    volumes: dict = {}

    # ── PostgreSQL + pgvector ──
    services["postgres"] = {
        "image": "pgvector/pgvector:pg17",
        "ports": ["5491:5432"],
        "environment": [
            "POSTGRES_USER=beaver",
            "POSTGRES_PASSWORD=beaver",
            "POSTGRES_DB=beaver",
        ],
        "volumes": [
            "postgres_data:/var/lib/postgresql/data",
        ],
        "healthcheck": {
            "test": ["CMD-SHELL", "pg_isready -U beaver -d beaver"],
            "interval": "5s",
            "timeout": "5s",
            "retries": 5,
        },
        "restart": "unless-stopped",
    }
    volumes["postgres_data"] = None

    # ── Ollama (Embeddings) ──
    services["ollama"] = {
        "image": "ollama/ollama:latest",
        "ports": ["11491:11434"],
        "volumes": ["ollama_data:/root/.ollama"],
        "restart": "unless-stopped",
    }
    volumes["ollama_data"] = None

    # ── SGLang (LLM) ──
    if cfg.model:
        sglang_cmd = (
            f"python3 -m sglang.launch_server "
            f"--model-path {cfg.model.hf_id} "
            f"--host 0.0.0.0 "
            f"--port 30000"
        )
        services["sglang"] = {
            "image": "lmsysorg/sglang:latest",
            "ports": ["30091:30000"],
            "volumes": ["sglang_cache:/root/.cache/huggingface"],
            "command": sglang_cmd,
            "deploy": {
                "resources": {
                    "reservations": {
                        "devices": [
                            {
                                "driver": "nvidia",
                                "count": "all",
                                "capabilities": ["gpu"],
                            }
                        ]
                    }
                }
            },
            "ipc": "host",
            "restart": "unless-stopped",
        }
        volumes["sglang_cache"] = None

    # ── Telegram MCP (separate container) ──
    telegram_mcps = [m for m in cfg.mcps if m.name == "Telegram"]
    if telegram_mcps:
        tg_env = cfg.mcp_env.get("Telegram", {})
        env_list = [f"{k}={v}" for k, v in tg_env.items()]
        services["telegram-mcp"] = {
            "build": {
                "context": ".",
                "dockerfile": "docker/telegram-mcp.Dockerfile",
            },
            "environment": env_list,
            "ports": ["3001:3001"],
            "restart": "unless-stopped",
        }

    # ── Beaver API ──
    api_env = [
        "API_HOST=0.0.0.0",
        "API_PORT=8741",
        "DATABASE_URL=postgresql+asyncpg://beaver:beaver@postgres:5432/beaver",
        f"SGLANG_URL=http://sglang:30000",
        "OLLAMA_URL=http://ollama:11434",
        "DEBUG=false",
    ]

    if cfg.embedding:
        api_env.append(f"EMBEDDING_MODEL={cfg.embedding.ollama_model}")
        api_env.append(f"EMBEDDING_DIM={cfg.embedding.dim}")

    api_depends: dict = {
        "postgres": {"condition": "service_healthy"},
        "ollama": {"condition": "service_started"},
    }

    services["api"] = {
        "build": {
            "context": ".",
            "dockerfile": "docker/api.Dockerfile",
        },
        "ports": ["8741:8741"],
        "depends_on": api_depends,
        "environment": api_env,
        "volumes": ["./uploads:/app/uploads"],
        "restart": "unless-stopped",
    }

    # ── Beaver Worker ──
    worker_env = [
        "DATABASE_URL=postgresql+asyncpg://beaver:beaver@postgres:5432/beaver",
        "OLLAMA_URL=http://ollama:11434",
    ]
    if cfg.embedding:
        worker_env.append(f"EMBEDDING_MODEL={cfg.embedding.ollama_model}")
        worker_env.append(f"EMBEDDING_DIM={cfg.embedding.dim}")

    worker_depends: dict = {
        "postgres": {"condition": "service_healthy"},
        "ollama": {"condition": "service_started"},
    }

    services["worker"] = {
        "build": {
            "context": ".",
            "dockerfile": "docker/worker.Dockerfile",
        },
        "depends_on": worker_depends,
        "environment": worker_env,
        "volumes": ["./uploads:/app/uploads"],
        "restart": "unless-stopped",
    }

    return {"services": services, "volumes": volumes}


def generate_env(cfg: InstallConfig) -> str:
    """Generate .env file content for local (non-Docker) development."""
    lines = [
        "# Generated by beaver install",
        "",
        "# Server",
        "API_HOST=0.0.0.0",
        "API_PORT=8741",
        "DEBUG=false",
        "",
        "# Database",
        "DATABASE_URL=postgresql+asyncpg://beaver:beaver@localhost:5491/beaver",
        "",
    ]

    lines.extend([
        "# Vector Store (pgvector — uses same database)",
        "VECTOR_COLLECTION=beaver_knowledge",
        "",
    ])

    lines.extend([
        "# LLM Backend (SGLang)",
        "SGLANG_URL=http://localhost:30091",
        f"DEFAULT_MODEL={cfg.model.hf_id if cfg.model else 'beaver-default'}",
        "",
        "# Embeddings (Ollama)",
        "OLLAMA_URL=http://localhost:11491",
    ])

    if cfg.embedding:
        lines.append(f"EMBEDDING_MODEL={cfg.embedding.ollama_model}")
        lines.append(f"EMBEDDING_DIM={cfg.embedding.dim}")

    lines.extend([
        "",
        "# RAG Parameters",
        "CHUNK_SIZE=512",
        "CHUNK_OVERLAP=50",
        "TOP_K=5",
        "",
        "# Limits",
        "MAX_UPLOAD_MB=100",
        "",
    ])

    return "\n".join(lines)


def write_install_files(cfg: InstallConfig) -> tuple[Path, Path]:
    """Write docker-compose.install.yml and .env.install to output_dir."""
    compose = generate_compose(cfg)
    compose_path = cfg.output_dir / "docker-compose.install.yml"
    env_path = cfg.output_dir / ".env.install"

    with open(compose_path, "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

    with open(env_path, "w") as f:
        f.write(generate_env(cfg))

    # Also write config.json for the CLI client
    client_cfg = {
        "api_url": "http://localhost:8741",
        "model": cfg.model.hf_id if cfg.model else None,
        "embedding_model": cfg.embedding.ollama_model if cfg.embedding else None,
        "vector_store": cfg.vector_store.name if cfg.vector_store else None,
        "mcps": [m.name for m in cfg.mcps],
    }
    config_dir = Path.home() / ".beaver"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(client_cfg, f, indent=2)

    return compose_path, env_path
