from typing import Any
from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from beaver.db.models import Document
from beaver.config import get_settings
from beaver.services.embeddings import get_embeddings
from beaver.services.vectorstore import get_vectorstore

cfg = get_settings()


class KnowledgeService:
    def __init__(self, embeddings=None, vectorstore=None):
        self.embeddings = embeddings or get_embeddings()
        self.vectorstore = vectorstore or get_vectorstore()
        self.collection = cfg.qdrant_collection

    async def init(self):
        await self.vectorstore.init()

    async def add_document(
        self,
        session: AsyncSession,
        user_id: str,
        filename: str,
        filepath: str,
        file_type: str,
    ) -> Document:
        doc = Document(
            user_id=user_id,
            filename=filename,
            filepath=filepath,
            file_type=file_type,
            status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc

    async def index_chunks(
        self, document_id: str, user_id: str, chunks: list[str], metadata: dict | None = None
    ) -> int:
        if not chunks:
            return 0

        vecs = await self.embeddings.embed_batch(chunks)
        ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        payloads = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "chunk_index": i,
                "text": c,
                **(metadata or {}),
            }
            for i, c in enumerate(chunks)
        ]
        await self.vectorstore.upsert(self.collection, ids, vecs, payloads)
        return len(chunks)

    async def search(
        self, query: str, user_id: str, top_k: int | None = None, score_threshold: float = 0.5
    ) -> list[dict[str, Any]]:
        top_k = top_k or cfg.top_k
        qvec = (await self.embeddings.embed(query))[0]

        results = await self.vectorstore.search(
            self.collection,
            qvec,
            top_k=top_k,
            filters={"user_id": user_id},
            score_threshold=score_threshold,
        )

        return [
            {
                "id": r["id"],
                "score": r["score"],
                "text": r["payload"].get("text", ""),
                "document_id": r["payload"].get("document_id"),
                "chunk_index": r["payload"].get("chunk_index"),
                "metadata": {
                    k: v for k, v in r["payload"].items()
                    if k not in ("text", "document_id", "user_id", "chunk_index")
                },
            }
            for r in results
        ]

    async def delete_document(
        self,
        session: AsyncSession,
        document_id: str,
        user_id: str,
    ) -> bool:
        # delete vectors
        await self.vectorstore.delete(
            self.collection, filters={"document_id": document_id, "user_id": user_id}
        )
        # delete db record
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc:
            await session.delete(doc)
            await session.commit()
            return True
        return False

    async def list_documents(
        self, session: AsyncSession, user_id: str, status: str | None = None
    ) -> list[Document]:
        stmt = select(Document).where(Document.user_id == user_id)
        if status:
            stmt = stmt.where(Document.status == status)
        stmt = stmt.order_by(Document.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        session: AsyncSession,
        document_id: str,
        status: str,
        chunk_count: int | None = None,
        error: str | None = None,
    ):
        stmt = select(Document).where(Document.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            return

        doc.status = status
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if error is not None:
            doc.error_message = error
        if status == "indexed":
            doc.indexed_at = datetime.now(UTC)
        await session.commit()


_knowledge: KnowledgeService | None = None


def get_knowledge() -> KnowledgeService:
    global _knowledge
    if _knowledge is None:
        _knowledge = KnowledgeService()
    return _knowledge
