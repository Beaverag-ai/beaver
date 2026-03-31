from __future__ import annotations

import asyncio
import logging
import argparse
import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

import uvicorn

from beaver.config import get_settings


def setup_logging(debug: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def run_api():
    cfg = get_settings()
    setup_logging(cfg.debug)
    uvicorn.run(
        "beaver.api.app:app",
        host=cfg.api_host,
        port=cfg.api_port,
        workers=cfg.api_workers,
        reload=cfg.debug,
    )


def run_worker():
    from beaver.workers.indexer import run_worker as start_worker
    cfg = get_settings()
    setup_logging(cfg.debug)
    start_worker()


async def run_migrations():
    from beaver.migrations.runner import run_migrations
    await run_migrations()


async def init_admin():
    from beaver.db.models import User
    from beaver.api.auth import create_api_key
    from beaver.db.session import get_session_context

    await run_migrations()

    email = input("Admin email: ").strip()
    if not email:
        print("Email is required")
        return

    name = input("Admin name (optional): ").strip() or None

    async with get_session_context() as session:
        user = User(email=email, name=name, role="admin")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"\nCreated admin user: {user.id}")

        raw_key, _ = await create_api_key(
            session,
            str(user.id),
            "Admin Key",
            "chat,knowledge,functions",
        )
        print(f"\nAPI Key (save this, it won't be shown again):\n  {raw_key}")


def main():
    parser = argparse.ArgumentParser(
        description="Beaver - Self-hosted RAG platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CLI commands:
  beaver install               Interactive setup wizard
  beaver chat [message]        Chat with the LLM (interactive if no message)
  beaver upload <file>         Upload a file to the knowledge base
  beaver documents             List uploaded documents
  beaver search <query>        Search the knowledge base
  beaver mcp servers           List MCP servers
  beaver mcp tools             List available MCP tools
  beaver mcp call <tool> <json>  Call an MCP tool
  beaver models                List available models
  beaver status                Check service health
""",
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # Server commands
    sub.add_parser("api", help="Run the API server")
    sub.add_parser("worker", help="Run the indexing worker")
    sub.add_parser("init", help="Initialize admin user")
    sub.add_parser("migrate", help="Run database migrations")

    # Installer
    sub.add_parser("install", help="Interactive setup wizard")

    # CLI client commands
    chat_p = sub.add_parser("chat", help="Chat with the LLM")
    chat_p.add_argument("message", nargs="*", help="Message (omit for interactive mode)")

    upload_p = sub.add_parser("upload", help="Upload a file to the knowledge base")
    upload_p.add_argument("file", nargs="*", help="File path to upload")

    sub.add_parser("documents", help="List uploaded documents")

    search_p = sub.add_parser("search", help="Search the knowledge base")
    search_p.add_argument("query", nargs="*", help="Search query")

    mcp_p = sub.add_parser("mcp", help="MCP server and tool management")
    mcp_p.add_argument("subcommand", nargs="*", help="servers | tools | call <name> <json>")

    sub.add_parser("models", help="List available models")
    sub.add_parser("status", help="Check service health")

    args = parser.parse_args()

    match args.command:
        # ── Server commands ──
        case "api":
            run_api()
        case "worker":
            run_worker()
        case "init":
            asyncio.run(init_admin())
        case "migrate":
            asyncio.run(run_migrations())

        # ── Installer ──
        case "install":
            from beaver.installer import run_installer
            run_installer()

        # ── CLI client commands ──
        case "chat":
            from beaver.cli.client import cmd_chat
            cmd_chat(args.message or [])
        case "upload":
            from beaver.cli.client import cmd_upload
            cmd_upload(args.file or [])
        case "documents":
            from beaver.cli.client import cmd_documents
            cmd_documents([])
        case "search":
            from beaver.cli.client import cmd_search
            cmd_search(args.query or [])
        case "mcp":
            from beaver.cli.client import cmd_mcp
            cmd_mcp(args.subcommand or [])
        case "models":
            from beaver.cli.client import cmd_models
            cmd_models([])
        case "status":
            from beaver.cli.client import cmd_status
            cmd_status([])

        case _:
            parser.print_help()


if __name__ == "__main__":
    main()
