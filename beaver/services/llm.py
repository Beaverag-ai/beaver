import json
from typing import Any, AsyncIterator

import httpx

from beaver.config import get_settings

cfg = get_settings()


class SGLangProvider:
    """Talks to SGLang or any OpenAI-compatible backend."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or cfg.sglang_url).rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kw,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        payload = {
            "model": model or cfg.default_model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            **kw,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        if stream:
            return self._stream(payload)

        r = await self._client.post(f"{self.base_url}/v1/chat/completions", json=payload)
        r.raise_for_status()
        return r.json()

    async def _stream(self, payload: dict) -> AsyncIterator[dict[str, Any]]:
        async with self._client.stream(
            "POST", f"{self.base_url}/v1/chat/completions", json=payload
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    pass  # skip malformed chunks

    async def list_models(self) -> list[dict[str, Any]]:
        r = await self._client.get(f"{self.base_url}/v1/models")
        r.raise_for_status()
        return r.json().get("data", [])

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self.base_url}/health")
            return r.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()


# module-level singleton
_llm: SGLangProvider | None = None


def get_llm() -> SGLangProvider:
    global _llm
    if _llm is None:
        _llm = SGLangProvider()
    return _llm


async def close_llm():
    global _llm
    if _llm:
        await _llm.close()
        _llm = None
