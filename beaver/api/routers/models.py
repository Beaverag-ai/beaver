from __future__ import annotations

import time

from fastapi import APIRouter

from beaver.api.auth import OptionalAuth
from beaver.api.deps import LLM
from beaver.core.schemas import ModelInfo, ModelListResponse

router = APIRouter(tags=["Models"])


@router.get("/models", response_model=ModelListResponse)
async def list_models(auth: OptionalAuth, llm: LLM):
    try:
        backend = await llm.list_models()
    except Exception:
        backend = []

    now = int(time.time())
    models = [
        ModelInfo(id="beaver-default", created=now, owned_by="beaver"),
        ModelInfo(id="beaver-embed", created=now, owned_by="beaver"),
    ]

    for m in backend:
        mid = m.get("id") or m.get("name", "")
        if mid:
            models.append(
                ModelInfo(
                    id=mid,
                    created=m.get("created", now),
                    owned_by=m.get("owned_by", "sglang"),
                )
            )

    return ModelListResponse(data=models)


@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str, auth: OptionalAuth):
    return ModelInfo(id=model_id, created=int(time.time()), owned_by="beaver")
