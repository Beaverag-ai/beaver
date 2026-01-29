import asyncio
import logging
import argparse

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
    parser = argparse.ArgumentParser(description="Beaver - Self-hosted RAG platform")
    sub = parser.add_subparsers(dest="command", help="Command to run")

    sub.add_parser("api", help="Run the API server")
    sub.add_parser("worker", help="Run the indexing worker")
    sub.add_parser("init", help="Initialize admin user")
    sub.add_parser("migrate", help="Run database migrations")

    args = parser.parse_args()

    match args.command:
        case "api":
            run_api()
        case "worker":
            run_worker()
        case "init":
            asyncio.run(init_admin())
        case "migrate":
            asyncio.run(run_migrations())
        case _:
            run_api()  # default to api


if __name__ == "__main__":
    main()
