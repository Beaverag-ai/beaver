# Beaver

Your own self-hosted **agentic AI stack**, in one box. Beaver bundles an LLM server, embeddings, a vector store, document ingestion, and Model Context Protocol (MCP) tool integrations behind a single OpenAI-compatible API — so you can chat with your private documents, drive real tools (Telegram, Slack, Gmail, GitHub, the filesystem), and run everything on your own hardware. No data leaves the machine unless you tell it to.

The goal is simple: **everything you'd get from a hosted assistant, but local, swappable, and yours.** Pick the LLM, pick the embeddings, pick the tools — the installer wires it together and the CLI lets you use it from the terminal.

## Quick Start

### Install the CLI

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv with Python 3.12 and install beaver
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

### Option A: Interactive Installer (Recommended)

```bash
beaver install
```

The installer walks you through choosing your stack:

1. **LLM Model** — served via SGLang (Linux + NVIDIA GPU) or Ollama (macOS / no GPU)
2. **MCP Integrations** — Telegram Bot, Telegram MCP, Slack, Gmail, GitHub, Filesystem
3. **Vector Storage** — pgvector (built into PostgreSQL)
4. **Embedding Model** — served via Ollama

It generates a `docker-compose.install.yml`, starts all services, pulls models, creates an admin user, and registers your MCP servers — all automatically.

### LLM backend: SGLang vs Ollama

Beaver picks the LLM backend based on your platform:

| Platform | Backend | Where the model comes from |
|---|---|---|
| Linux + NVIDIA GPU | **SGLang** | HuggingFace repo ID (e.g. `Qwen/Qwen2.5-7B-Instruct`) |
| macOS / no GPU | **Ollama** | Ollama model alias (e.g. `qwen3:32b`) |

> **macOS note:** SGLang requires an NVIDIA GPU, so on a Mac the installer routes the LLM through Ollama. **The model you select must be a valid Ollama model alias from the [Ollama library](https://ollama.com/library)** — for example `qwen3:32b`, `qwen3:8b`, `llama3.1:8b`, `mistral:7b`, `deepseek-r1:8b`. HuggingFace repo IDs (`org/model`) are not valid Ollama tags and won't pull. If you choose "Custom" in the installer on macOS, enter an Ollama tag, not an HF ID.

### Option B: Manual Setup

```bash
# Start the base stack (postgres + ollama + api + worker)
docker compose up -d

# Wait for postgres to be ready, then init the admin user
docker compose exec api python -m beaver.main init

# Save the API key it prints out!
```

That's it. The API is running at `http://localhost:8741`.

For a richer setup (LLM server, Telegram, custom embeddings), use `beaver install` instead — the manual flow is intentionally minimal.

## CLI Commands

After installation, the `beaver` CLI gives you full control from the terminal.

### Chat

```bash
# One-shot message
beaver chat "What is the capital of France?"

# Interactive chat session (multi-turn, with history)
beaver chat
```

### Knowledge Base

```bash
# Upload a file (pdf, docx, txt, md, xlsx, pptx, and more)
beaver upload report.pdf

# List all uploaded documents and their indexing status
beaver documents

# Semantic search across your knowledge base
beaver search "quarterly revenue figures"
```

### MCP Tools

```bash
# List registered MCP servers
beaver mcp servers

# List all available tools across all MCP servers
beaver mcp tools

# Call a tool directly
beaver mcp call send_message '{"chat_id": "@username", "message": "Hello from Beaver!"}'
beaver mcp call get_chats '{"limit": 10}'
beaver mcp call search_messages '{"chat_id": "@channel", "query": "meeting"}'
```

### Other

```bash
# List available LLM models
beaver models

# Check service health
beaver status
```

## Test It

```bash
# Health check
curl http://localhost:8741/health

# Chat (replace with your API key)
curl http://localhost:8741/v1/chat/completions \
  -H "Authorization: Bearer bvr_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "beaver-default",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Architecture

```
                ┌──────────────┐    ┌──────────────┐
                │  beaver CLI  │    │ Telegram Bot │
                └──────┬───────┘    └──────┬───────┘
                       │                   │
        ┌──────────────▼───────────────────▼──────────────┐
        │              Beaver API (FastAPI)               │
        │                localhost:8741                   │
        │  /v1/chat/completions  /v1/embeddings           │
        │  /v1/knowledge/*       /v1/functions/*          │
        │  /v1/mcp/*             /v1/auth/*  /metrics/*   │
        └───┬────────────┬───────────┬────────────┬───────┘
            │            │           │            │
   ┌────────▼─────┐ ┌────▼─────┐ ┌───▼────┐ ┌─────▼──────┐
   │   SGLang     │ │  Ollama  │ │Postgres│ │ MCP servers│
   │ (Linux+GPU)  │ │ (LLM on  │ │   +    │ │ (Telegram, │
   │ HF model     │ │  macOS,  │ │pgvector│ │  Slack,    │
   │              │ │ embeds)  │ │        │ │  Gmail...) │
   └──────────────┘ └──────────┘ └────────┘ └────────────┘
                                      ▲
                              ┌───────┴────────┐
                              │ Beaver Worker  │
                              │ (doc indexing) │
                              └────────────────┘
```

## Configuration

All config is via environment variables. The installer writes `.env.install` for you; for manual setups, set these directly.

Key ones:
- `DATABASE_URL` — Postgres connection string
- `SGLANG_URL` — LLM backend URL (points at SGLang on Linux, Ollama on macOS)
- `OLLAMA_URL` — Ollama URL for embeddings (and for the LLM on macOS)
- `DEFAULT_MODEL` — Model identifier (HF repo ID for SGLang, Ollama alias for Ollama)
- `EMBEDDING_MODEL` — Ollama embedding model alias (e.g. `nomic-embed-text`)
- `EMBEDDING_DIM` — Embedding vector dimension
- `VECTOR_COLLECTION` — pgvector collection name (default: `beaver_knowledge`)
- `PERPLEXITY_API_KEY` — Optional, for the built-in `web_search` function

## API Endpoints

### Chat (OpenAI-compatible)

```bash
POST /v1/chat/completions
{
  "model": "beaver-default",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true,
  "use_knowledge": true  # RAG from your docs
}
```

### Knowledge Base

```bash
# Upload a doc
curl -X POST http://localhost:8741/v1/knowledge/documents \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@mydoc.pdf"

# List docs
GET /v1/knowledge/documents

# Search without chat
POST /v1/knowledge/query
{"query": "how does X work?", "top_k": 5}
```

### Functions

Built-in functions:
- `search_knowledge` — Search your docs
- `web_search` — Perplexity-powered web search
- `summarize` — Summarize text

```bash
# List available functions
GET /v1/functions

# Execute one
POST /v1/functions/web_search/execute
{"arguments": {"query": "latest news about..."}}

# Register your own
POST /v1/functions
{
  "name": "my_func",
  "description": "Does something cool",
  "parameters": {"type": "object", "properties": {...}},
  "endpoint": "https://my-server.com/webhook"
}
```

### MCP Servers

Connect to external MCP servers and use their tools in chat:

```bash
# Connect a server (stdio transport)
POST /v1/mcp/servers
{
  "name": "my-mcp",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
}

# Connect a server (SSE transport, e.g. telegram-mcp)
POST /v1/mcp/servers
{
  "name": "telegram",
  "transport": "sse",
  "url": "http://telegram-mcp:3001/sse"
}

# List tools from connected servers
GET /v1/mcp/tools

# Call a tool directly
POST /v1/mcp/tools/read_file/call
{"arguments": {"path": "/some/file.txt"}}
```

#### Telegram Bot

The lightweight option: pick **Telegram Bot** in the installer and provide a `TELEGRAM_BOT_TOKEN` (from [@BotFather](https://t.me/BotFather)). Beaver runs a small bot container that lets users chat with the assistant and upload files via Telegram.

#### Telegram MCP

The full option: pick **Telegram MCP** to expose your own Telegram account as 70+ tools (send messages, manage chats, search, contacts, media). Beaver runs [telegram-mcp](https://github.com/chigwell/telegram-mcp) in a separate container with an SSE bridge.

**Prerequisites:**
1. Get your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from [my.telegram.org/apps](https://my.telegram.org/apps).
2. Generate a session string by running `python3 generate_tg_session.py` from the repo root.

The installer will prompt for these credentials during setup.

### Auth

```bash
# Get current user
GET /v1/auth/me

# Create new API key
POST /v1/auth/api-keys
{"name": "my-app", "scopes": "chat,knowledge"}

# List keys
GET /v1/auth/api-keys

# Revoke
DELETE /v1/auth/api-keys/{id}
```

## Development

### Local Setup (without Docker)

```bash
# You need postgres (with pgvector) and ollama running locally

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .

# Or use uv sync for reproducible installs (if uv.lock exists)
uv sync

# Run migrations
python -m beaver.main migrate

# Create admin
python -m beaver.main init

# Start API
python -m beaver.main api

# In another terminal, start the indexer worker
python -m beaver.main worker
```

### Project Structure

```
beaver/
├── api/           # FastAPI app, routes, auth
├── cli/           # CLI client (chat, upload, search, mcp)
├── core/          # Schemas, exceptions, interfaces
├── db/            # SQLAlchemy models, session
├── installer/     # Interactive setup wizard
├── mcp/           # MCP client for external servers
├── migrations/    # SQL migration files
├── services/      # LLM, embeddings, knowledge, etc
└── workers/       # Background document indexer
docker/
├── api.Dockerfile
├── worker.Dockerfile
├── telegram-bot.Dockerfile         # Telegram bot container
├── telegram-bot.py                 # Bot implementation
├── telegram-mcp.Dockerfile         # Telegram MCP container
└── telegram-mcp-bridge.py          # SSE bridge for stdio MCP
```

### Installer-Generated Files

When you run `beaver install`, the following files are created:

| File | Purpose |
|------|---------|
| `docker-compose.install.yml` | Docker Compose with all selected services |
| `.env.install` | Environment variables for local development |
| `.env` | Runtime values (e.g. `BEAVER_API_KEY`) consumed by docker-compose |
| `~/.beaver/config.json` | CLI client configuration (API URL, API key, model) |

### Extending

The core services use Protocol classes so you can swap implementations:

```python
from beaver.core.interfaces import LLMProvider

class MyCustomLLM(LLMProvider):
    async def chat(self, messages, **kwargs):
        # your implementation
        pass

    async def list_models(self):
        return [{"id": "my-model"}]

    async def health(self):
        return True

    async def close(self):
        pass

# Use it
from beaver.services.llm import _instance
_instance = MyCustomLLM()
```

Same pattern works for `EmbeddingsProvider` and `VectorStore`.

## Docker Services

A full installation includes the following containers (some are optional based on installer choices):

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **api** | Custom (Dockerfile) | 8741 | Beaver API server |
| **worker** | Custom (Dockerfile) | — | Background document indexing |
| **postgres** | pgvector/pgvector:pg17 | 5491 | Metadata + vector storage (pgvector) |
| **ollama** | ollama/ollama:latest | 11491 | Embeddings (and LLM on macOS) |
| **sglang** | lmsysorg/sglang:latest | 30091 | LLM inference (Linux + NVIDIA GPU only) |
| **telegram-bot** | Custom (Dockerfile) | — | Telegram bot frontend (optional) |
| **telegram-mcp** | Custom (Dockerfile) | 3001 | Telegram-as-tools MCP with SSE bridge (optional) |

### Managing Services

```bash
# View logs
docker compose -f docker-compose.install.yml logs -f

# Stop everything
docker compose -f docker-compose.install.yml down

# Restart a single service
docker compose -f docker-compose.install.yml restart api

# Pull the embedding model manually
docker compose -f docker-compose.install.yml exec ollama ollama pull nomic-embed-text
```

### Clean Reinstall

To wipe everything (containers, volumes, images, build cache) and start fresh:

```bash
docker compose -f docker-compose.install.yml down -v --rmi all
docker builder prune -f
beaver install
```

## License

MIT
