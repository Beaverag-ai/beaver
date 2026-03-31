from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from beaver.config import get_settings

cfg = get_settings()


class QdrantStore:
    def __init__(self, host: str | None = None, port: int | None = None):
        self._client = AsyncQdrantClient(
            host=host or cfg.qdrant_host,
            port=port or cfg.qdrant_port,
        )

    async def init(self):
        """Create collection if it doesn't exist."""
        collections = await self._client.get_collections()
        existing = [c.name for c in collections.collections]
        if cfg.qdrant_collection not in existing:
            await self._client.create_collection(
                collection_name=cfg.qdrant_collection,
                vectors_config=VectorParams(
                    size=cfg.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ):
        points = [
            PointStruct(id=id_, vector=vec, payload=pl)
            for id_, vec, pl in zip(ids, vectors, payloads)
        ]
        await self._client.upsert(collection_name=collection, points=points)

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        qf = None
        if filters:
            qf = Filter(
                must=[
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
            )

        results = await self._client.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=qf,
        )
        return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]

    async def delete(
        self,
        collection: str,
        ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ):
        if filters:
            f = Filter(
                must=[
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
            )
            await self._client.delete(collection_name=collection, points_selector=f)
        elif ids:
            await self._client.delete(collection_name=collection, points_selector=ids)

    async def health(self) -> bool:
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False

    async def close(self):
        await self._client.close()


_store: QdrantStore | None = None


def get_vectorstore() -> QdrantStore:
    global _store
    if _store is None:
        _store = QdrantStore()
    return _store


async def close_vectorstore():
    global _store
    if _store:
        await _store.close()
        _store = None
