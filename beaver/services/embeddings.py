from __future__ import annotations

import httpx

from beaver.config import get_settings

cfg = get_settings()


class OllamaEmbeddings:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or cfg.ollama_url).rstrip("/")
        self.model = cfg.embedding_model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def embed(
        self,
        texts: str | list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]

        model = model or self.model
        out = []
        for text in texts:
            r = await self._client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            r.raise_for_status()
            out.append(r.json()["embedding"])
        return out

    async def embed_batch(
        self, texts: list[str], model: str | None = None, batch_size: int = 10
    ) -> list[list[float]]:
        # ollama doesn't support batching natively, so we just loop
        out = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            out.extend(await self.embed(batch, model))
        return out

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self.base_url}/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()


_embeddings: OllamaEmbeddings | None = None


def get_embeddings() -> OllamaEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OllamaEmbeddings()
    return _embeddings


async def close_embeddings():
    global _embeddings
    if _embeddings:
        await _embeddings.close()
        _embeddings = None
