"""Interactive installer CLI for Beaver."""

from __future__ import annotations

import sys

# Force unbuffered stdout so prompts appear immediately in containers
sys.stdout.reconfigure(line_buffering=True)

from beaver.installer.catalog import (
    EMBEDDING_MODELS,
    MCPS,
    MODELS,
    VECTOR_STORES,
)
from beaver.installer.compose import InstallConfig, write_install_files
from beaver.installer.prompts import (
    ask_secret,
    banner,
    confirm,
    error,
    header,
    info,
    select_many,
    select_one,
    success,
    warn,
    BOLD,
    CYAN,
    DIM,
    GREEN,
    RESET,
    YELLOW,
)
from beaver.installer.setup import run_setup


def run_installer() -> None:
    """Main installer entry point."""
    banner()

    cfg = InstallConfig()

    # ── Step 1: Choose LLM Model ──
    header("Step 1/4: Choose LLM Model")
    cfg.model = select_one(
        "LLM Model",
        "Served via SGLang, loaded from HuggingFace",
        MODELS,
        name_fn=lambda m: m.name,
        desc_fn=lambda m: m.description,
        default_fn=lambda m: m.default,
    )

    # ── Step 2: Choose MCP Integrations ──
    header("Step 2/4: Choose MCP Integrations")
    cfg.mcps = select_many(
        "MCP Servers",
        "External tool integrations via Model Context Protocol",
        MCPS,
        name_fn=lambda m: m.name,
        desc_fn=lambda m: m.description,
        default_fn=lambda m: m.default,
    )

    # Collect MCP credentials
    for mcp in cfg.mcps:
        if mcp.env_vars:
            print(f"\n  {BOLD}{mcp.name} requires credentials:{RESET}")
            env = {}
            for var in mcp.env_vars:
                val = ask_secret(f"  {var}")
                if val:
                    env[var] = val
            if env:
                cfg.mcp_env[mcp.name] = env
            else:
                warn(f"No credentials provided for {mcp.name}. You can set them later in .env.install")

    # ── Step 3: Choose Vector Storage ──
    header("Step 3/4: Choose Vector Storage")
    cfg.vector_store = select_one(
        "Vector Database",
        "Storage backend for document embeddings",
        VECTOR_STORES,
        name_fn=lambda v: v.name,
        desc_fn=lambda v: v.description,
        default_fn=lambda v: v.default,
    )

    # ── Step 4: Choose Embedding Model ──
    header("Step 4/4: Choose Embedding Model")
    cfg.embedding = select_one(
        "Embedding Model",
        "Runs on Ollama for document and query embeddings",
        EMBEDDING_MODELS,
        name_fn=lambda e: e.name,
        desc_fn=lambda e: e.description,
        default_fn=lambda e: e.default,
    )

    # ── Summary ──
    header("Configuration Summary")
    print(f"""
  {BOLD}Model:{RESET}      {cfg.model.name}
  {BOLD}MCPs:{RESET}       {', '.join(m.name for m in cfg.mcps)}
  {BOLD}Storage:{RESET}    {cfg.vector_store.name}
  {BOLD}Embedding:{RESET}  {cfg.embedding.name}
""")

    if not confirm("Proceed with installation?"):
        warn("Installation cancelled")
        return

    # ── Generate Files ──
    header("Generating Configuration")
    compose_path, env_path = write_install_files(cfg)
    success(f"Docker Compose: {compose_path}")
    success(f"Environment:    {env_path}")
    success(f"Client config:  ~/.beaver/config.json")

    # ── Start & Setup ──
    if confirm("Start services now?"):
        header("Starting Services")
        ok = run_setup(cfg)

        if ok:
            print(f"""
{GREEN}{'━' * 50}
  Beaver is ready!
{'━' * 50}{RESET}

  {BOLD}API URL:{RESET}  http://localhost:8741
  {BOLD}Config:{RESET}   ~/.beaver/config.json

  {BOLD}Quick start:{RESET}
    beaver chat "Hello, how are you?"
    beaver upload document.pdf
    beaver search "what is in the document?"
    beaver mcp tools
    beaver mcp call send_message '{{"chat_id": "username", "message": "Hi!"}}'

  {BOLD}Logs:{RESET}
    docker compose -f docker-compose.install.yml logs -f

  {BOLD}Stop:{RESET}
    docker compose -f docker-compose.install.yml down
""")
        else:
            warn("Some steps had issues. Check the output above.")
            info("You can view logs with:")
            info("  docker compose -f docker-compose.install.yml logs -f")
    else:
        print(f"""
  {BOLD}To start manually:{RESET}
    docker compose -f docker-compose.install.yml up -d --build
    beaver init

  {BOLD}Then use:{RESET}
    beaver chat "Hello!"
    beaver upload file.pdf
    beaver search "query"
""")
