from __future__ import annotations

"""Component catalog for Beaver installer."""

from dataclasses import dataclass, field


@dataclass
class Model:
    name: str
    hf_id: str
    description: str
    default: bool = False


@dataclass
class MCP:
    name: str
    description: str
    repo: str | None = None
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    default: bool = False


@dataclass
class VectorStore:
    name: str
    image: str
    port: int
    description: str
    cloud: bool = False
    default: bool = False


@dataclass
class EmbeddingModel:
    name: str
    ollama_model: str
    dim: int
    description: str
    default: bool = False


MODELS = [
    Model(
        name="Qwen/Qwen3.5-35B-A3B-FP8",
        hf_id="Qwen/Qwen3.5-35B-A3B-FP8",
        description="Qwen 3.5 35B MoE (FP8) — fast, high quality",
        default=True,
    ),
    Model(
        name="Qwen/Qwen2.5-7B-Instruct",
        hf_id="Qwen/Qwen2.5-7B-Instruct",
        description="Qwen 2.5 7B — good balance of speed and quality",
    ),
    Model(
        name="meta-llama/Llama-3.1-8B-Instruct",
        hf_id="meta-llama/Llama-3.1-8B-Instruct",
        description="Llama 3.1 8B — Meta's open model",
    ),
    Model(
        name="mistralai/Mistral-7B-Instruct-v0.3",
        hf_id="mistralai/Mistral-7B-Instruct-v0.3",
        description="Mistral 7B v0.3 — efficient instruction model",
    ),
    Model(
        name="deepseek-ai/DeepSeek-R1-0528",
        hf_id="deepseek-ai/DeepSeek-R1-0528",
        description="DeepSeek R1 — strong reasoning model",
    ),
]

MCPS = [
    MCP(
        name="Telegram Bot",
        description="Chat with Beaver and upload files via Telegram bot",
        env_vars=["TELEGRAM_BOT_TOKEN"],
        default=True,
    ),
    MCP(
        name="Telegram MCP",
        description="Access your Telegram account as tools (send messages, search chats)",
        repo="https://github.com/chigwell/telegram-mcp",
        transport="stdio",
        command="uv",
        args=["--directory", "/opt/telegram-mcp", "run", "main.py"],
        env_vars=["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING"],
    ),
    MCP(
        name="Slack",
        description="Slack workspace messaging and management",
    ),
    MCP(
        name="Gmail",
        description="Read and send emails via Gmail",
    ),
    MCP(
        name="GitHub",
        description="GitHub repositories, issues, and PRs",
    ),
    MCP(
        name="Filesystem",
        description="Local filesystem read/write access",
    ),
]

VECTOR_STORES = [
    VectorStore(
        name="pgvector",
        image="",
        port=0,
        description="PostgreSQL vector extension (built into Postgres, no extra container)",
        default=True,
    ),
    VectorStore(
        name="Qdrant",
        image="qdrant/qdrant:latest",
        port=6333,
        description="High-performance vector search engine",
    ),
    VectorStore(
        name="Chroma",
        image="chromadb/chroma:latest",
        port=8000,
        description="Open-source embedding database",
    ),
    VectorStore(
        name="Weaviate",
        image="semitechnologies/weaviate:latest",
        port=8080,
        description="AI-native vector database",
    ),
    VectorStore(
        name="Pinecone",
        image="",
        port=0,
        description="Cloud-hosted vector database",
        cloud=True,
    ),
]

EMBEDDING_MODELS = [
    EmbeddingModel(
        name="nomic-embed-text",
        ollama_model="nomic-embed-text",
        dim=768,
        description="Nomic Embed Text — general-purpose embeddings",
        default=True,
    ),
    EmbeddingModel(
        name="mxbai-embed-large",
        ollama_model="mxbai-embed-large",
        dim=1024,
        description="MixedBread Embed Large",
    ),
    EmbeddingModel(
        name="all-minilm",
        ollama_model="all-minilm",
        dim=384,
        description="All-MiniLM — lightweight, fast embeddings",
    ),
    EmbeddingModel(
        name="snowflake-arctic-embed",
        ollama_model="snowflake-arctic-embed",
        dim=1024,
        description="Snowflake Arctic Embed",
    ),
]
