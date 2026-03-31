from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from beaver import __version__
from beaver.config import get_settings
from beaver.db.session import init_db, close_db
from beaver.core.exceptions import BeaverError
from beaver.services.llm import close_llm
from beaver.services.knowledge import get_knowledge
from beaver.services.embeddings import close_embeddings
from beaver.services.vectorstore import close_vectorstore
from beaver.mcp.manager import close_mcp_manager

cfg = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    kb = get_knowledge()
    await kb.init()
    yield
    await close_mcp_manager()
    await close_llm()
    await close_embeddings()
    await close_vectorstore()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Beaver",
        description="Self-hosted RAG platform with OpenAI-compatible API",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(BeaverError)
    async def handle_beaver_error(request: Request, exc: BeaverError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": __version__}

    # register all routers
    from beaver.api.routers import (
        auth_routes,
        chat,
        embeddings,
        functions,
        knowledge,
        mcp,
        metrics,
        models,
    )

    app.include_router(chat.router, prefix="/v1")
    app.include_router(embeddings.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(knowledge.router, prefix="/v1")
    app.include_router(functions.router, prefix="/v1")
    app.include_router(mcp.router, prefix="/v1")
    app.include_router(auth_routes.router, prefix="/v1")
    app.include_router(metrics.router)

    return app


app = create_app()
