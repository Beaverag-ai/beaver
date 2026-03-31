from __future__ import annotations

import asyncio
import logging
from typing import Any
from pathlib import Path

from beaver.config import get_settings
from beaver.db.session import get_session_context
from beaver.services.knowledge import get_knowledge

cfg = get_settings()
log = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    size = chunk_size or cfg.chunk_size
    overlap = overlap or cfg.chunk_overlap

    if len(text) <= size:
        return [text]

    chunks = []
    pos = 0
    while pos < len(text):
        end = pos + size
        if end < len(text):
            # try to break at sentence/paragraph
            for sep in [". ", ".\n", "\n\n", "\n", " "]:
                idx = text[pos:end].rfind(sep)
                if idx > size // 2:
                    end = pos + idx + len(sep)
                    break

        chunk = text[pos:end].strip()
        if chunk:
            chunks.append(chunk)
        pos = end - overlap

    return chunks


async def extract_text(path: Path) -> str:
    ext = path.suffix.lower()

    # plain text files
    if ext in {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    # try unstructured for everything else
    try:
        from unstructured.partition.auto import partition
        elements = partition(str(path))
        return "\n\n".join(str(el) for el in elements)
    except ImportError:
        log.warning("unstructured not installed, falling back to text read")
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        log.error(f"Error extracting text from {path}: {e}")
        raise


async def index_document(doc_id: str, user_id: str, filepath: str) -> dict[str, Any]:
    kb = get_knowledge()
    path = Path(filepath)

    async with get_session_context() as session:
        try:
            await kb.update_status(session, doc_id, "indexing")

            text = await extract_text(path)
            if not text.strip():
                await kb.update_status(session, doc_id, "failed", error="No text content")
                return {"status": "failed", "error": "No text content"}

            chunks = chunk_text(text)
            meta = {"filename": path.name, "file_type": path.suffix.lower()}

            count = await kb.index_chunks(doc_id, user_id, chunks, meta)
            await kb.update_status(session, doc_id, "indexed", chunk_count=count)

            return {"status": "indexed", "chunk_count": count}

        except Exception as e:
            log.exception(f"Error indexing document {doc_id}")
            await kb.update_status(session, doc_id, "failed", error=str(e))
            return {"status": "failed", "error": str(e)}


async def process_pending():
    kb = get_knowledge()
    async with get_session_context() as session:
        # get all pending docs across all users
        docs = await kb.list_documents(session, user_id=None, status="pending")
        for doc in docs:
            log.info(f"Processing: {doc.filename}")
            await index_document(str(doc.id), str(doc.user_id), doc.filepath)


async def worker_loop(poll_interval: int = 5):
    log.info("Starting indexer worker")
    kb = get_knowledge()
    await kb.init()

    while True:
        try:
            await process_pending()
        except Exception as e:
            log.exception(f"Worker error: {e}")
        await asyncio.sleep(poll_interval)


def run_worker():
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    run_worker()
