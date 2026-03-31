from __future__ import annotations

from fastapi import APIRouter

from beaver.api.auth import Auth
from beaver.api.deps import Embeddings
from beaver.core.schemas import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
)

router = APIRouter(tags=["Embeddings"])


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest, auth: Auth, embeddings: Embeddings):
    texts = request.input if isinstance(request.input, list) else [request.input]
    vecs = await embeddings.embed(texts)

    # rough token estimate (words)
    tokens = sum(len(t.split()) for t in texts)

    return EmbeddingResponse(
        data=[EmbeddingData(index=i, embedding=v) for i, v in enumerate(vecs)],
        model=request.model,
        usage=EmbeddingUsage(prompt_tokens=tokens, total_tokens=tokens),
    )
