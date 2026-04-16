"""Interactive installer CLI for Beaver."""

from __future__ import annotations

import platform
import sys

# Force unbuffered stdout so prompts appear immediately in containers
sys.stdout.reconfigure(line_buffering=True)

from beaver.installer.catalog import (
    EMBEDDING_MODELS,
    MCPS,
    MODELS,
    OLLAMA_LLM_MODELS,
    VECTOR_STORES,
    Model,
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


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _select_model() -> Model:
    """Pick from the catalog, or enter a custom model alias.

    On macOS, uses Ollama (SGLang needs NVIDIA GPUs). Elsewhere, uses SGLang
    with HuggingFace repos.
    """
    if _is_macos():
        items = OLLAMA_LLM_MODELS
        subtitle = "Served via Ollama (macOS — SGLang requires NVIDIA GPU)"
        custom_label = "Enter an Ollama model tag (e.g. qwen3:14b)"
    else:
        items = MODELS
        subtitle = "Served via SGLang, loaded from HuggingFace"
        custom_label = "Enter a HuggingFace model ID (e.g. dmayboroda/model)"

    print(f"\n  {BOLD}LLM Model{RESET}")
    info(subtitle)
    print()

    default_idx = 0
    for i, m in enumerate(items):
        marker = f"{GREEN}*{RESET}" if m.default else " "
        print(f"  [{marker}] {i + 1}. {BOLD}{m.name}{RESET}")
        print(f"       {DIM}{m.description}{RESET}")
        if m.default:
            default_idx = i

    custom_idx = len(items) + 1
    print(f"  [ ] {custom_idx}. {BOLD}Custom{RESET}")
    print(f"       {DIM}{custom_label}{RESET}")

    print()
    while True:
        raw = input(f"  Select (1-{custom_idx}) [{default_idx + 1}]: ").strip()
        if not raw:
            return items[default_idx]
        try:
            idx = int(raw) - 1
        except ValueError:
            error(f"Please enter a number between 1 and {custom_idx}")
            continue
        if 0 <= idx < len(items):
            return items[idx]
        if idx == len(items):
            return _prompt_custom_ollama() if _is_macos() else _prompt_custom_hf()
        error(f"Please enter a number between 1 and {custom_idx}")


def _prompt_custom_hf() -> Model:
    """Prompt for an HF model alias like 'org/name'."""
    while True:
        alias = input("  HuggingFace model ID (org/name): ").strip()
        parts = alias.split("/")
        if len(parts) == 2 and all(p.strip() for p in parts):
            return Model(
                name=alias,
                hf_id=alias,
                description="Custom HuggingFace model",
                provider="sglang",
            )
        error("Enter a valid HF model ID like 'org/model-name'")


def _prompt_custom_ollama() -> Model:
    """Prompt for an Ollama registry tag like 'name' or 'name:tag'."""
    while True:
        alias = input("  Ollama model tag (e.g. qwen3:32b): ").strip()
        if alias and " " not in alias:
            return Model(
                name=alias,
                hf_id=alias,
                description="Custom Ollama model",
                provider="ollama",
            )
        error("Enter a valid Ollama tag like 'qwen3:32b' or 'llama3.1:8b'")


def run_installer() -> None:
    """Main installer entry point."""
    banner()

    cfg = InstallConfig()

    # ── Step 1: Choose LLM Model ──
    header("Step 1/4: Choose LLM Model")
    cfg.model = _select_model()

    # ── Step 2: Choose MCP Integrations ──
    header("Step 2/4: Choose MCP Integrations")
    cfg.mcps = select_many(
        "MCP Servers",
        "External tool integrations via Model Context Protocol",
        MCPS,
        name_fn=lambda m: m.name,
        desc_fn=lambda m: m.description,
        default_fn=lambda m: m.default,
        allow_skip=True,
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
