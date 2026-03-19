"""Beaver CLI client — interact with the Beaver API from the terminal."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx


CONFIG_PATH = Path.home() / ".beaver" / "config.json"

# ANSI
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"{RED}No config found at {CONFIG_PATH}{RESET}")
        print(f"Run {BOLD}beaver install{RESET} first, or create config manually.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_client(cfg: dict) -> tuple[httpx.Client, dict]:
    base = cfg.get("api_url", "http://localhost:8741")
    api_key = cfg.get("api_key", "")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    client = httpx.Client(base_url=base, headers=headers, timeout=120)
    return client, headers


# ── Chat ──

def cmd_chat(args: list[str]) -> None:
    """Send a chat message or start interactive chat."""
    cfg = load_config()
    client, _ = get_client(cfg)

    if args:
        message = " ".join(args)
        _send_chat(client, cfg, message)
    else:
        _interactive_chat(client, cfg)


def _send_chat(client: httpx.Client, cfg: dict, message: str) -> None:
    payload = {
        "model": cfg.get("model", "beaver-default"),
        "messages": [{"role": "user", "content": message}],
        "use_knowledge": True,
        "stream": False,
    }
    try:
        r = client.post("/v1/chat/completions", json=payload)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        print(f"\n{CYAN}Beaver:{RESET} {content}\n")
    except httpx.HTTPStatusError as e:
        print(f"{RED}Error:{RESET} {e.response.status_code} — {e.response.text}")
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


def _interactive_chat(client: httpx.Client, cfg: dict) -> None:
    print(f"{CYAN}Beaver Chat{RESET} (type 'exit' or Ctrl+C to quit)\n")
    messages = []
    while True:
        try:
            user_input = input(f"{GREEN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_input or user_input.lower() in ("exit", "quit"):
            break

        messages.append({"role": "user", "content": user_input})
        payload = {
            "model": cfg.get("model", "beaver-default"),
            "messages": messages,
            "use_knowledge": True,
            "stream": False,
        }
        try:
            r = client.post("/v1/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": content})
            print(f"{CYAN}Beaver:{RESET} {content}\n")
        except Exception as e:
            print(f"{RED}Error:{RESET} {e}\n")


# ── Upload ──

def cmd_upload(args: list[str]) -> None:
    """Upload a file to the knowledge base."""
    if not args:
        print(f"{RED}Usage:{RESET} beaver upload <file_path>")
        sys.exit(1)

    file_path = Path(args[0])
    if not file_path.exists():
        print(f"{RED}File not found:{RESET} {file_path}")
        sys.exit(1)

    cfg = load_config()
    client, _ = get_client(cfg)

    print(f"Uploading {BOLD}{file_path.name}{RESET}...")
    try:
        with open(file_path, "rb") as f:
            r = client.post(
                "/v1/knowledge/documents",
                files={"file": (file_path.name, f)},
            )
        r.raise_for_status()
        data = r.json()
        print(f"{GREEN}Uploaded!{RESET}")
        print(f"  Document ID: {data.get('id', 'N/A')}")
        print(f"  Status: {data.get('status', 'N/A')}")
        print(f"  The document will be indexed in the background.")
    except httpx.HTTPStatusError as e:
        print(f"{RED}Upload failed:{RESET} {e.response.status_code} — {e.response.text}")
    except Exception as e:
        print(f"{RED}Upload failed:{RESET} {e}")


# ── Documents ──

def cmd_documents(args: list[str]) -> None:
    """List documents in the knowledge base."""
    cfg = load_config()
    client, _ = get_client(cfg)

    try:
        r = client.get("/v1/knowledge/documents")
        r.raise_for_status()
        docs = r.json()
        if not docs:
            print("No documents found.")
            return
        print(f"\n{'ID':<38} {'Status':<10} {'Chunks':<8} {'Filename'}")
        print("─" * 80)
        for d in docs:
            print(f"{d['id']:<38} {d['status']:<10} {d.get('chunk_count', '-'):<8} {d['filename']}")
        print()
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


# ── Search ──

def cmd_search(args: list[str]) -> None:
    """Search the knowledge base."""
    if not args:
        print(f"{RED}Usage:{RESET} beaver search <query>")
        sys.exit(1)

    query = " ".join(args)
    cfg = load_config()
    client, _ = get_client(cfg)

    try:
        r = client.post("/v1/knowledge/query", json={"query": query, "top_k": 5})
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            print("No results found.")
            return
        print(f"\n{BOLD}Search results for:{RESET} {query}\n")
        for i, res in enumerate(results, 1):
            score = res.get("score", 0)
            text = res.get("text", "")[:200]
            print(f"  {CYAN}[{i}]{RESET} (score: {score:.3f})")
            print(f"      {text}...")
            print()
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


# ── MCP ──

def cmd_mcp(args: list[str]) -> None:
    """MCP server and tool management."""
    if not args:
        _mcp_help()
        return

    sub = args[0]
    rest = args[1:]

    match sub:
        case "servers":
            _mcp_servers()
        case "tools":
            _mcp_tools()
        case "call":
            _mcp_call(rest)
        case _:
            _mcp_help()


def _mcp_help():
    print(f"""
{BOLD}MCP Commands:{RESET}
  beaver mcp servers           List registered MCP servers
  beaver mcp tools             List available MCP tools
  beaver mcp call <tool> <json_args>  Call an MCP tool
""")


def _mcp_servers():
    cfg = load_config()
    client, _ = get_client(cfg)
    try:
        r = client.get("/v1/mcp/servers")
        r.raise_for_status()
        servers = r.json()
        if not servers:
            print("No MCP servers registered.")
            return
        print(f"\n{'ID':<38} {'Name':<15} {'Transport':<10} {'Active'}")
        print("─" * 75)
        for s in servers:
            print(f"{s['id']:<38} {s['name']:<15} {s['transport']:<10} {s.get('is_active', True)}")
        print()
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


def _mcp_tools():
    cfg = load_config()
    client, _ = get_client(cfg)
    try:
        r = client.get("/v1/mcp/tools")
        r.raise_for_status()
        tools = r.json()
        if not tools:
            print("No MCP tools available.")
            return
        print(f"\n{BOLD}Available MCP Tools:{RESET}\n")
        for t in tools:
            print(f"  {CYAN}{t['name']}{RESET}")
            if t.get("description"):
                print(f"    {DIM}{t['description']}{RESET}")
            print(f"    Server: {t.get('server_name', 'unknown')}")
            print()
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


def _mcp_call(args: list[str]):
    if len(args) < 1:
        print(f"{RED}Usage:{RESET} beaver mcp call <tool_name> [json_args]")
        return

    tool_name = args[0]
    arguments = {}
    if len(args) > 1:
        try:
            arguments = json.loads(args[1])
        except json.JSONDecodeError:
            print(f"{RED}Invalid JSON arguments{RESET}")
            return

    cfg = load_config()
    client, _ = get_client(cfg)
    try:
        r = client.post(
            f"/v1/mcp/tools/{tool_name}/call",
            json={"arguments": arguments},
        )
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            print(f"{RED}Error:{RESET} {data['error']}")
        else:
            result = data.get("result")
            if isinstance(result, (dict, list)):
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(result)
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


# ── Models ──

def cmd_models(args: list[str]) -> None:
    """List available models."""
    cfg = load_config()
    client, _ = get_client(cfg)
    try:
        r = client.get("/v1/models")
        r.raise_for_status()
        data = r.json()
        models = data.get("data", [])
        if not models:
            print("No models available.")
            return
        print(f"\n{BOLD}Available Models:{RESET}\n")
        for m in models:
            print(f"  {m.get('id', 'unknown')}")
        print()
    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


# ── Status ──

def cmd_status(args: list[str]) -> None:
    """Check Beaver service status."""
    cfg = load_config()
    base = cfg.get("api_url", "http://localhost:8741")
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"{GREEN}Beaver is running{RESET} (v{data.get('version', '?')})")
        else:
            print(f"{YELLOW}Beaver responded with status {r.status_code}{RESET}")
    except Exception:
        print(f"{RED}Beaver is not reachable{RESET} at {base}")
