from typing import Any, Literal
from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_calls: list["ToolCall"] | None = None
    tool_call_id: str | None = None


class FunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class FunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class ChatCompletionRequest(BaseModel):
    model: str = "beaver-default"
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = None
    stream: bool = False
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: str | list[str] | None = None
    user: str | None = None
    use_knowledge: bool = True
    knowledge_top_k: int = 5


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage | None = None


class ChatCompletionChunkDelta(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatCompletionChunkChoice(BaseModel):
    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


class EmbeddingRequest(BaseModel):
    model: str = "beaver-embed"
    input: str | list[str]
    encoding_format: Literal["float", "base64"] = "float"


class EmbeddingData(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "beaver"


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelInfo]


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime


class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime
    indexed_at: datetime | None = None


class KnowledgeQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    score_threshold: float = 0.5


class KnowledgeQueryResult(BaseModel):
    text: str
    score: float
    document_id: str
    chunk_index: int
    metadata: dict[str, Any] = {}


class KnowledgeQueryResponse(BaseModel):
    results: list[KnowledgeQueryResult]
    query: str


class APIKeyCreate(BaseModel):
    name: str
    scopes: str = "chat,knowledge,functions"
    expires_in_days: int | None = None


class APIKeyResponse(BaseModel):
    id: str
    key: str
    key_prefix: str
    name: str
    scopes: str
    created_at: datetime
    expires_at: datetime | None = None


class APIKeyInfo(BaseModel):
    id: str
    key_prefix: str
    name: str
    scopes: str
    created_at: datetime
    expires_at: datetime | None = None
    is_active: bool


class UserInfo(BaseModel):
    id: str
    email: str
    name: str | None = None
    role: str
    created_at: datetime


class FunctionCreate(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    endpoint: str | None = None


class FunctionInfo(BaseModel):
    id: str
    name: str
    description: str
    parameters: dict[str, Any]
    endpoint: str | None = None
    is_builtin: bool
    is_active: bool


class FunctionExecuteRequest(BaseModel):
    arguments: dict[str, Any]


class FunctionExecuteResponse(BaseModel):
    result: Any
    error: str | None = None


class MCPServerCreate(BaseModel):
    name: str
    transport: Literal["stdio", "sse", "websocket"]
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None


class MCPServerInfo(BaseModel):
    id: str
    name: str
    transport: str
    command: str | None = None
    url: str | None = None
    is_active: bool
    created_at: datetime


class MCPToolInfo(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    server_id: str
    server_name: str


class MCPToolCallRequest(BaseModel):
    arguments: dict[str, Any]


class MCPToolCallResponse(BaseModel):
    result: Any
    error: str | None = None


class ErrorDetail(BaseModel):
    message: str
    type: str
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


ChatMessage.model_rebuild()
ToolCall.model_rebuild()
ToolDefinition.model_rebuild()
