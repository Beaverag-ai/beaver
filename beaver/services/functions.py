from __future__ import annotations

import logging
from typing import Any, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from beaver.config import get_settings
from beaver.db.models import Function
from beaver.services.llm import get_llm
from beaver.services.knowledge import get_knowledge

log = logging.getLogger(__name__)
cfg = get_settings()


async def search_knowledge(query: str, user_id: str, top_k: int = 5) -> dict[str, Any]:
    kb = get_knowledge()
    hits = await kb.search(query=query, user_id=user_id, top_k=top_k)
    return {
        "results": [
            {
                "text": h["text"],
                "score": h["score"],
                "document_id": h["document_id"],
            }
            for h in hits
        ]
    }


async def web_search(query: str, num_results: int = 5) -> dict[str, Any]:
    if not cfg.perplexity_api_key:
        return {"results": [], "error": "Perplexity API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg.perplexity_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-sonar-small-128k-online",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful search assistant. Provide concise, factual answers with sources.",
                        },
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.2,
                    "return_citations": True,
                },
            )
            r.raise_for_status()
            data = r.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = data.get("citations", [])
            return {"answer": content, "citations": citations[:num_results], "model": data.get("model", "")}

    except httpx.HTTPStatusError as e:
        log.error(f"Perplexity API error: {e.response.status_code}")
        return {"results": [], "error": f"API error: {e.response.status_code}"}
    except Exception as e:
        log.error(f"Web search error: {e}")
        return {"results": [], "error": str(e)}


async def summarize(text: str, max_length: int = 200) -> dict[str, Any]:
    llm = get_llm()
    try:
        resp = await llm.chat(
            messages=[
                {"role": "system", "content": f"Summarize the following text in {max_length} words or less. Be concise."},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            stream=False,
        )
        content = resp["choices"][0]["message"]["content"] if "choices" in resp else ""
        return {"summary": content}
    except Exception as e:
        log.error(f"Summarize error: {e}")
        return {"summary": "", "error": str(e)}


# builtin function definitions
BUILTIN_FUNCTIONS: dict[str, dict[str, Any]] = {
    "search_knowledge": {
        "description": "Search the knowledge base for relevant documents",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "top_k": {"type": "integer", "description": "Number of results to return", "default": 5},
            },
            "required": ["query"],
        },
        "handler": search_knowledge,
    },
    "web_search": {
        "description": "Search the web using Perplexity AI",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "num_results": {"type": "integer", "description": "Number of citations to return", "default": 5},
            },
            "required": ["query"],
        },
        "handler": web_search,
    },
    "summarize": {
        "description": "Summarize a piece of text",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to summarize"},
                "max_length": {"type": "integer", "description": "Maximum length of summary in words", "default": 200},
            },
            "required": ["text"],
        },
        "handler": summarize,
    },
}


class FunctionService:
    def __init__(self):
        self._handlers: dict[str, Callable] = {
            name: fn["handler"] for name, fn in BUILTIN_FUNCTIONS.items()
        }

    async def register_builtins(self, session: AsyncSession) -> None:
        for name, defn in BUILTIN_FUNCTIONS.items():
            result = await session.execute(select(Function).where(Function.name == name))
            if not result.scalar_one_or_none():
                session.add(
                    Function(
                        name=name,
                        description=defn["description"],
                        parameters_schema=defn["parameters"],
                        is_builtin=True,
                    )
                )
        await session.commit()

    async def create(
        self,
        session: AsyncSession,
        user_id: str,
        name: str,
        description: str,
        parameters: dict[str, Any],
        endpoint: str | None = None,
    ) -> Function:
        func = Function(
            user_id=user_id,
            name=name,
            description=description,
            parameters_schema=parameters,
            endpoint=endpoint,
            is_builtin=False,
        )
        session.add(func)
        await session.commit()
        await session.refresh(func)
        return func

    async def get(
        self,
        session: AsyncSession,
        name: str,
        user_id: str | None = None,
    ) -> Function | None:
        result = await session.execute(
            select(Function).where(Function.name == name, Function.is_active == True)
        )
        func = result.scalar_one_or_none()
        # don't return user functions that belong to someone else
        if func and not func.is_builtin and func.user_id != user_id:
            return None
        return func

    async def list(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        include_builtin: bool = True,
    ) -> list[Function]:
        stmt = select(Function).where(Function.is_active == True)
        if not include_builtin:
            stmt = stmt.where(Function.is_builtin == False)
        if user_id:
            stmt = stmt.where((Function.is_builtin == True) | (Function.user_id == user_id))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def execute(
        self,
        session: AsyncSession,
        name: str,
        arguments: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        func = await self.get(session, name, user_id)
        if not func:
            return {"error": f"Function '{name}' not found"}

        # builtin handlers
        if func.is_builtin and name in self._handlers:
            handler = self._handlers[name]
            if name == "search_knowledge":
                arguments["user_id"] = user_id
            try:
                return await handler(**arguments)
            except Exception as e:
                log.exception(f"Error executing function {name}")
                return {"error": str(e)}

        # custom endpoint
        if func.endpoint:
            try:
                async with httpx.AsyncClient(timeout=30.0) as c:
                    r = await c.post(func.endpoint, json=arguments)
                    r.raise_for_status()
                    return r.json()
            except Exception as e:
                log.error(f"Error calling function endpoint: {e}")
                return {"error": str(e)}

        return {"error": f"Function '{name}' has no handler or endpoint"}

    def to_openai_tools(self, functions: list[Function]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": f.name,
                    "description": f.description,
                    "parameters": f.parameters_schema,
                },
            }
            for f in functions
        ]


_instance: FunctionService | None = None


def get_functions() -> FunctionService:
    global _instance
    if _instance is None:
        _instance = FunctionService()
    return _instance
