from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, File, UploadFile

from beaver.api.auth import Auth
from beaver.api.deps import DBSession, Knowledge
from beaver.config import get_settings
from beaver.core.exceptions import NotFoundError, ValidationError
from beaver.core.schemas import (
    DocumentInfo,
    DocumentUploadResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeQueryResult,
    MCPIndexRequest,
    MCPIndexResponse,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])
cfg = get_settings()

ALLOWED_EXT = {
    ".txt",
    ".md",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".html",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".css",
}


def validate_file(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValidationError(f"File type '{ext}' not allowed")
    return ext


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    auth: Auth,
    knowledge: Knowledge,
    session: DBSession,
    file: UploadFile = File(...),
):
    auth.require_scope("knowledge")

    if not file.filename:
        raise ValidationError("Filename is required")

    ext = validate_file(file.filename)
    fid = uuid4().hex
    path = cfg.uploads_dir / auth.user_id / f"{fid}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(path, "wb") as f:
        content = await file.read()
        if len(content) > cfg.max_upload_mb * 1024 * 1024:
            raise ValidationError(f"File too large. Max: {cfg.max_upload_mb}MB")
        await f.write(content)

    doc = await knowledge.add_document(session, auth.user_id, file.filename, str(path), ext)

    return DocumentUploadResponse(
        id=str(doc.id),
        filename=doc.filename,
        status=doc.status,
        created_at=doc.created_at,
    )


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(
    auth: Auth,
    knowledge: Knowledge,
    session: DBSession,
    status: str | None = None,
):
    auth.require_scope("knowledge")
    docs = await knowledge.list_documents(session, auth.user_id, status)
    return [
        DocumentInfo(
            id=str(d.id),
            filename=d.filename,
            file_type=d.file_type,
            status=d.status,
            chunk_count=d.chunk_count,
            created_at=d.created_at,
            indexed_at=d.indexed_at,
        )
        for d in docs
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    auth: Auth,
    knowledge: Knowledge,
    session: DBSession,
):
    auth.require_scope("knowledge")
    if not await knowledge.delete_document(session, document_id, auth.user_id):
        raise NotFoundError("Document", document_id)
    return {"deleted": True, "id": document_id}


@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    request: KnowledgeQueryRequest,
    auth: Auth,
    knowledge: Knowledge,
):
    auth.require_scope("knowledge")
    results = await knowledge.search(
        request.query,
        auth.user_id,
        request.top_k,
        request.score_threshold,
    )
    return KnowledgeQueryResponse(
        results=[
            KnowledgeQueryResult(
                text=r["text"],
                score=r["score"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                metadata=r.get("metadata", {}),
            )
            for r in results
        ],
        query=request.query,
    )


@router.post("/index-from-mcp", response_model=MCPIndexResponse)
async def index_from_mcp(
    request: MCPIndexRequest,
    auth: Auth,
    knowledge: Knowledge,
    session: DBSession,
):
    auth.require_scope("knowledge")

    from beaver.mcp.registry import get_mcp_registry
    from beaver.workers.indexer import chunk_text

    reg = get_mcp_registry()

    # resolve server_id if not provided
    server_id = request.server_id
    if not server_id:
        tools = await reg.discover_tools(session, auth.user_id)
        match = [t for t in tools if t["name"] == request.tool_name]
        if not match:
            raise NotFoundError("MCP tool", request.tool_name)
        server_id = match[0]["server_id"]

    # call the MCP tool
    result = await reg.call_tool(session, server_id, request.tool_name, request.tool_arguments)

    # extract text from MCP content blocks
    text_parts = []
    if isinstance(result, list):
        for item in result:
            if hasattr(item, "text"):
                text_parts.append(item.text)
            elif isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
    elif isinstance(result, str):
        text_parts.append(result)

    text = "\n\n".join(text_parts)
    if not text.strip():
        raise ValidationError("MCP tool returned no text content")

    # create document record
    doc_name = request.document_name or f"mcp:{request.tool_name}"
    doc = await knowledge.add_document(
        session,
        auth.user_id,
        filename=doc_name,
        filepath=f"mcp://{request.tool_name}",
        file_type="mcp",
    )
    doc.source = "mcp"
    await session.commit()
    await session.refresh(doc)

    doc_id = str(doc.id)

    # chunk, embed, and index
    chunks = chunk_text(text)
    meta = {
        "source": "mcp",
        "mcp_tool": request.tool_name,
        "mcp_server_id": server_id,
        "filename": doc_name,
    }
    chunk_count = await knowledge.index_chunks(doc_id, auth.user_id, chunks, meta)
    await knowledge.update_status(session, doc_id, "indexed", chunk_count=chunk_count)

    return MCPIndexResponse(
        id=doc_id,
        document_name=doc_name,
        status="indexed",
        chunk_count=chunk_count,
        created_at=doc.created_at,
    )
