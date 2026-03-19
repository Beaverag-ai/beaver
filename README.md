# Beaver

Self-hosted RAG platform with an OpenAI-compatible API. Drop in your documents, connect MCP servers, and query everything through a familiar chat interface.

## Quick Start

### Option A: Interactive Installer (Recommended)

```bash
beaver install
```

The installer walks you through choosing your stack:

1. **LLM Model** — served via SGLang, loaded from HuggingFace
2. **MCP Integrations** — Telegram, Slack, Gmail, GitHub, Filesystem
3. **Vector Storage** — Qdrant, Pinecone, Chroma, Weaviate
4. **Embedding Model** — served via Ollama

It generates a `docker-compose.install.yml`, starts all services, pulls models, creates an admin user, and registers your MCP servers — all automatically.

### Option B: Manual Setup

```bash
# Clone and setup
cp .env.example .env
# Edit .env with your settings (especially PERPLEXITY_API_KEY for web search)

# Start everything
docker compose up -d

# Wait for postgres to be ready, then init admin
docker compose exec api python -m beaver.main init

# Save the API key it prints out!
```

That's it. API is running at `http://localhost:8741`.

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
                        ┌──────────────────┐
                        │   beaver CLI     │
                        │ chat/upload/mcp  │
                        └────────┬─────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│                    Beaver API (FastAPI)                      │
│                      localhost:8741                          │
├─────────────────────────────────────────────────────────────┤
│  /v1/chat/completions   │  /v1/embeddings  │  /v1/models    │
│  /v1/knowledge/*        │  /v1/functions/* │  /v1/auth/*    │
│  /v1/mcp/servers/*      │  /metrics/*      │                │
└───────┬─────────────────┴────────┬─────────┴───────┬────────┘
        │                          │                 │
┌───────▼────────┐   ┌────────────▼──────┐   ┌──────▼──────┐
│     SGLang     │   │      Ollama       │   │   Qdrant    │
│ (LLM from HF) │   │   (embeddings)    │   │  (vectors)  │
│  :30091        │   │    :11491         │   │   :6391     │
└────────────────┘   └──────────────────┘   └─────────────┘
        │
┌───────▼────────────────┐
│   telegram-mcp         │
│ (SSE bridge, :3001)    │
│ Telegram API access    │
└────────────────────────┘
```

## Configuration

All config is via environment variables. See `.env.example` for the full list.

Key ones:
- `DATABASE_URL` - Postgres connection string
- `SGLANG_URL` - Your LLM server (OpenAI-compatible)
- `OLLAMA_URL` - Ollama for embeddings
- `PERPLEXITY_API_KEY` - For web search function
- `QDRANT_HOST` / `QDRANT_PORT` - Vector DB

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
- `search_knowledge` - Search your docs
- `web_search` - Perplexity-powered web search
- `summarize` - Summarize text

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

#### Telegram MCP

The installer can set up [telegram-mcp](https://github.com/chigwell/telegram-mcp) in a separate Docker container with an SSE bridge. It provides 70+ tools for Telegram including messaging, chat management, contacts, media, and search.

**Prerequisites:**
1. Get your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from [my.telegram.org/apps](https://my.telegram.org/apps)
2. Generate a session string by running the `session_string_generator.py` from the telegram-mcp repo

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
# You need postgres, qdrant, ollama running locally

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
├── telegram-mcp.Dockerfile      # Telegram MCP container
└── telegram-mcp-bridge.py       # SSE bridge for stdio MCP
```

### Installer-Generated Files

When you run `beaver install`, the following files are created:

| File | Purpose |
|------|---------|
| `docker-compose.install.yml` | Docker Compose with all selected services |
| `.env.install` | Environment variables for local development |
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

The full installation includes the following containers:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **api** | Custom (Dockerfile) | 8741 | Beaver API server |
| **worker** | Custom (Dockerfile) | — | Background document indexing |
| **postgres** | postgres:17-alpine | 5491 | Metadata database |
| **qdrant** | qdrant/qdrant:v1.12.1 | 6391 | Vector storage for embeddings |
| **ollama** | ollama/ollama:latest | 11491 | Embedding model server |
| **sglang** | lmsysorg/sglang:latest | 30091 | LLM inference (GPU required) |
| **telegram-mcp** | Custom (Dockerfile) | 3001 | Telegram MCP with SSE bridge |

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

## License

MIT
