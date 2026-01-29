import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from beaver.api.auth import Auth
from beaver.api.deps import DBSession, LLM, Knowledge
from beaver.core.schemas import (
    ChatMessage,
    ChatCompletionChunk,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatCompletionChunkDelta,
    ChatCompletionChunkChoice,
)

router = APIRouter(tags=["Chat"])


def build_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    parts = ["Here is relevant context from the knowledge base:\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] {r['text']}\n")
    return "\n".join(parts)


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    auth: Auth,
    llm: LLM,
    knowledge: Knowledge,
    session: DBSession,
):
    auth.require_scope("chat")

    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    # inject knowledge base context if enabled
    if request.use_knowledge and messages:
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if user_msgs:
            query = user_msgs[-1].get("content", "")
            if query:
                results = await knowledge.search(
                    query=query,
                    user_id=auth.user_id,
                    top_k=request.knowledge_top_k,
                )
                if results:
                    ctx = build_context(results)
                    # find system message or insert one
                    sys_idx = next(
                        (i for i, m in enumerate(messages) if m.get("role") == "system"),
                        None,
                    )
                    if sys_idx is not None:
                        messages[sys_idx]["content"] += f"\n\n{ctx}"
                    else:
                        messages.insert(0, {"role": "system", "content": ctx})

    tools = (
        [t.model_dump(exclude_none=True) for t in request.tools]
        if request.tools
        else None
    )

    if request.stream:
        return StreamingResponse(
            stream_response(
                llm,
                messages,
                request.model,
                request.temperature,
                request.max_tokens,
                tools,
            ),
            media_type="text/event-stream",
        )

    resp = await llm.chat(
        messages=messages,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=tools,
        stream=False,
    )

    # if backend already returns openai format, just forward it
    if "choices" in resp:
        return resp

    # otherwise wrap it
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid4().hex[:24]}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=resp.get("content", "")),
                finish_reason="stop",
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=resp.get("prompt_tokens", 0),
            completion_tokens=resp.get("completion_tokens", 0),
            total_tokens=resp.get("total_tokens", 0),
        ),
    )


async def stream_response(
    llm: LLM,
    messages: list[dict],
    model: str,
    temp: float,
    max_tokens: int | None,
    tools: list | None,
) -> AsyncIterator[str]:
    cid = f"chatcmpl-{uuid4().hex[:24]}"
    ts = int(time.time())

    # initial chunk with role
    init = ChatCompletionChunk(
        id=cid,
        created=ts,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(role="assistant"),
                finish_reason=None,
            )
        ],
    )
    yield f"data: {init.model_dump_json()}\n\n"

    async for chunk in await llm.chat(
        messages=messages,
        model=model,
        temperature=temp,
        max_tokens=max_tokens,
        tools=tools,
        stream=True,
    ):
        if "choices" not in chunk or not chunk["choices"]:
            continue

        c = chunk["choices"][0]
        delta = c.get("delta", {})
        out = ChatCompletionChunk(
            id=cid,
            created=ts,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content=delta.get("content")),
                    finish_reason=c.get("finish_reason"),
                )
            ],
        )
        yield f"data: {out.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"
