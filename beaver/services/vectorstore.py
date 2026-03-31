from __future__ import annotations

from typing import Any

import asyncpg

from beaver.config import get_settings

cfg = get_settings()


def _pg_url() -> str:
    """Convert SQLAlchemy async URL to plain postgresql:// for asyncpg."""
    return cfg.database_url.replace("postgresql+asyncpg://", "postgresql://")


class PgVectorStore:
    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(_pg_url(), min_size=2, max_size=10)
        return self._pool

    async def init(self):
        """Ensure pgvector extension and table exist (migrations handle this,
        but we verify connectivity)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for id_, vec, pl in zip(ids, vectors, payloads):
                    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
                    await conn.execute(
                        """
                        INSERT INTO vector_chunks (id, collection, embedding, document_id, user_id, chunk_index, text, metadata)
                        VALUES ($1, $2, $3::vector, $4, $5, $6, $7, $8::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            document_id = EXCLUDED.document_id,
                            user_id = EXCLUDED.user_id,
                            chunk_index = EXCLUDED.chunk_index,
                            text = EXCLUDED.text,
                            metadata = EXCLUDED.metadata
                        """,
                        id_,
                        collection,
                        vec_str,
                        pl.get("document_id"),
                        pl.get("user_id"),
                        pl.get("chunk_index"),
                        pl.get("text"),
                        _payload_to_metadata(pl),
                    )

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        vec_str = "[" + ",".join(str(v) for v in vector) + "]"

        # Build WHERE clause
        conditions = ["collection = $1"]
        params: list[Any] = [collection]
        idx = 2

        if filters:
            for key, value in filters.items():
                if key in ("user_id", "document_id"):
                    conditions.append(f"{key} = ${idx}")
                    params.append(str(value))
                    idx += 1
                else:
                    conditions.append(f"metadata->>'{key}' = ${idx}")
                    params.append(str(value))
                    idx += 1

        where = " AND ".join(conditions)

        # Cosine similarity: 1 - cosine_distance
        query = f"""
            SELECT id, 1 - (embedding <=> $%d::vector) AS score,
                   document_id, user_id, chunk_index, text, metadata
            FROM vector_chunks
            WHERE {where}
            ORDER BY embedding <=> $%d::vector
            LIMIT $%d
        """ % (idx, idx, idx + 1)

        params.append(vec_str)
        params.append(top_k)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            score = float(row["score"])
            if score_threshold is not None and score < score_threshold:
                continue
            payload = {
                "document_id": row["document_id"],
                "user_id": row["user_id"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
            }
            if row["metadata"]:
                import json
                meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                payload.update(meta)
            results.append({"id": row["id"], "score": score, "payload": payload})

        return results

    async def delete(
        self,
        collection: str,
        ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if filters:
                conditions = ["collection = $1"]
                params: list[Any] = [collection]
                idx = 2
                for key, value in filters.items():
                    if key in ("user_id", "document_id"):
                        conditions.append(f"{key} = ${idx}")
                        params.append(str(value))
                        idx += 1
                    else:
                        conditions.append(f"metadata->>'{key}' = ${idx}")
                        params.append(str(value))
                        idx += 1
                where = " AND ".join(conditions)
                await conn.execute(f"DELETE FROM vector_chunks WHERE {where}", *params)
            elif ids:
                await conn.execute(
                    "DELETE FROM vector_chunks WHERE id = ANY($1)",
                    ids,
                )

    async def health(self) -> bool:
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None


def _payload_to_metadata(payload: dict) -> str:
    """Extract extra metadata fields (not stored in dedicated columns) as JSON."""
    import json
    skip = {"document_id", "user_id", "chunk_index", "text"}
    meta = {k: v for k, v in payload.items() if k not in skip}
    return json.dumps(meta)


_store: PgVectorStore | None = None


def get_vectorstore() -> PgVectorStore:
    global _store
    if _store is None:
        _store = PgVectorStore()
    return _store


async def close_vectorstore():
    global _store
    if _store:
        await _store.close()
        _store = None
