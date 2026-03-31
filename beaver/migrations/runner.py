from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg

from beaver.config import get_settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent


async def get_connection() -> asyncpg.Connection:
    settings = get_settings()
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(url)


async def get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {row["version"] for row in rows}


async def run_migrations() -> None:
    conn = await get_connection()

    try:
        applied = await get_applied_migrations(conn)
        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for sql_file in sql_files:
            version = sql_file.stem
            if version in applied:
                logger.debug(f"Skipping {version} (already applied)")
                continue

            logger.info(f"Applying migration: {version}")
            sql = sql_file.read_text()

            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version,
                )

            logger.info(f"Applied: {version}")

        logger.info("All migrations complete")

    finally:
        await conn.close()


async def rollback_migration(version: str) -> None:
    conn = await get_connection()

    try:
        await conn.execute(
            "DELETE FROM schema_migrations WHERE version = $1",
            version,
        )
        logger.info(f"Rolled back migration record: {version}")

    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_migrations())


if __name__ == "__main__":
    main()
