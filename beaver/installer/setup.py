"""Post-startup setup: pull models, init admin, register MCPs."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

from beaver.installer.compose import InstallConfig
from beaver.installer.prompts import error, info, success, warn


COMPOSE_FILE = "docker-compose.install.yml"


def run_cmd(cmd: list[str], check: bool = True, capture: bool = False, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True, **kw)


def docker_compose(*args: str) -> subprocess.CompletedProcess:
    return run_cmd(["docker", "compose", "-f", COMPOSE_FILE, *args])


def start_services(cfg: InstallConfig) -> bool:
    """Build and start all containers."""
    info("Building and starting containers...")
    try:
        docker_compose("up", "-d", "--build")
        success("Containers started")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to start containers: {e}")
        return False


def wait_for_service(name: str, url: str, timeout: int = 120) -> bool:
    """Poll a health endpoint until it responds."""
    info(f"Waiting for {name}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=5)
            if r.status_code == 200:
                success(f"{name} is ready")
                return True
        except Exception:
            pass
        time.sleep(2)
    error(f"{name} did not become ready within {timeout}s")
    return False


def wait_for_all(cfg: InstallConfig) -> bool:
    """Wait for all services to be healthy."""
    ok = True

    # Postgres (check via docker)
    info("Waiting for PostgreSQL...")
    for _ in range(30):
        result = run_cmd(
            ["docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", "postgres",
             "pg_isready", "-U", "beaver"],
            check=False, capture=True,
        )
        if result.returncode == 0:
            success("PostgreSQL is ready")
            break
        time.sleep(2)
    else:
        error("PostgreSQL did not become ready")
        ok = False

    # Ollama
    if not wait_for_service("Ollama", "http://localhost:11491/api/tags", timeout=60):
        ok = False

    # Vector store
    if cfg.vector_store and cfg.vector_store.name == "Qdrant":
        if not wait_for_service("Qdrant", "http://localhost:6391/collections", timeout=60):
            ok = False

    # Beaver API
    if not wait_for_service("Beaver API", "http://localhost:8741/health", timeout=120):
        ok = False

    return ok


def pull_embedding_model(cfg: InstallConfig) -> bool:
    """Pull the embedding model into Ollama."""
    if not cfg.embedding:
        return True

    model = cfg.embedding.ollama_model
    info(f"Pulling embedding model: {model}")
    try:
        run_cmd([
            "docker", "compose", "-f", COMPOSE_FILE,
            "exec", "-T", "ollama",
            "ollama", "pull", model,
        ])
        success(f"Embedding model pulled: {model}")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to pull embedding model: {e}")
        return False


def init_beaver() -> str | None:
    """Run migrations and create admin user via the API.

    Returns the API key or None on failure.
    """
    info("Initializing Beaver (migrations + admin)...")

    try:
        # Run migrations via the API container
        run_cmd([
            "docker", "compose", "-f", COMPOSE_FILE,
            "exec", "-T", "api",
            "python", "-m", "beaver.main", "migrate",
        ])
        success("Migrations complete")
    except subprocess.CalledProcessError:
        warn("Migrations may have already run")

    # Create admin via the init command (non-interactive: pipe input)
    try:
        result = run_cmd(
            [
                "docker", "compose", "-f", COMPOSE_FILE,
                "exec", "-T", "api",
                "python", "-m", "beaver.main", "init",
            ],
            check=False,
            capture=True,
            input="admin@beaver.local\nAdmin\n",
        )
        output = result.stdout
        # Extract API key from output
        for line in output.splitlines():
            if line.strip().startswith("bvr_"):
                api_key = line.strip()
                success(f"Admin user created")
                # Save API key to client config
                config_path = Path.home() / ".beaver" / "config.json"
                if config_path.exists():
                    with open(config_path) as f:
                        client_cfg = json.load(f)
                    client_cfg["api_key"] = api_key
                    with open(config_path, "w") as f:
                        json.dump(client_cfg, f, indent=2)
                return api_key
        error("Could not extract API key from init output")
        info(f"Init output: {output}")
        return None
    except subprocess.CalledProcessError as e:
        error(f"Failed to init admin: {e}")
        return None


def register_telegram_mcp(api_key: str, cfg: InstallConfig) -> bool:
    """Register Telegram MCP server via the Beaver API."""
    telegram_mcps = [m for m in cfg.mcps if m.name == "Telegram"]
    if not telegram_mcps:
        return True

    tg = telegram_mcps[0]
    tg_env = cfg.mcp_env.get("Telegram", {})

    info("Registering Telegram MCP server...")

    # The MCP server runs in the telegram-mcp container, exposed via SSE on port 3001
    # But since we built it as a stdio server with an SSE bridge, we connect via SSE
    payload = {
        "name": "telegram",
        "transport": "sse",
        "url": "http://telegram-mcp:3001/sse",
    }

    try:
        r = httpx.post(
            "http://localhost:8741/v1/mcp/servers",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        if r.status_code in (200, 201):
            success("Telegram MCP registered")
            return True
        else:
            error(f"Failed to register Telegram MCP: {r.status_code} {r.text}")
            return False
    except Exception as e:
        error(f"Failed to register Telegram MCP: {e}")
        return False


def run_setup(cfg: InstallConfig) -> bool:
    """Full post-compose setup sequence."""
    if not start_services(cfg):
        return False

    if not wait_for_all(cfg):
        error("Some services failed to start. Check logs with:")
        info(f"  docker compose -f {COMPOSE_FILE} logs")
        return False

    if not pull_embedding_model(cfg):
        warn("Embedding model pull failed. You can retry manually:")
        info(f"  docker compose -f {COMPOSE_FILE} exec ollama ollama pull {cfg.embedding.ollama_model if cfg.embedding else ''}")

    api_key = init_beaver()
    if not api_key:
        warn("Admin init failed. Run manually:")
        info(f"  docker compose -f {COMPOSE_FILE} exec api python -m beaver.main init")
        return False

    register_telegram_mcp(api_key, cfg)

    return True
