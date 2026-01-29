# Beaver

Self-hosted RAG platform with an OpenAI-compatible API. Drop in your documents, connect MCP servers, and query everything through a familiar chat interface.

## Quick Start

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
┌─────────────────────────────────────────────────────────────┐
│                    Beaver API (FastAPI)                      │
│                      localhost:8741                          │
├─────────────────────────────────────────────────────────────┤
│  /v1/chat/completions   │  /v1/embeddings  │  /v1/models    │
│  /v1/knowledge/*        │  /v1/functions/* │  /v1/auth/*    │
│  /v1/mcp/servers/*      │  /metrics/*      │                │
└────────────┬────────────┴────────┬─────────┴───────┬────────┘
             │                     │                 │
    ┌────────▼────────┐   ┌───────▼───────┐   ┌─────▼─────┐
    │     SGLang      │   │    Ollama     │   │  Qdrant   │
    │  (LLM inference)│   │ (embeddings)  │   │ (vectors) │
    └─────────────────┘   └───────────────┘   └───────────┘
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
# Connect a server
POST /v1/mcp/servers
{
  "name": "my-mcp",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
}

# List tools from connected servers
GET /v1/mcp/tools

# Call a tool directly
POST /v1/mcp/tools/read_file/call
{"arguments": {"path": "/some/file.txt"}}
```

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
├── core/          # Schemas, exceptions, interfaces
├── db/            # SQLAlchemy models, session
├── mcp/           # MCP client for external servers
├── migrations/    # SQL migration files
├── services/      # LLM, embeddings, knowledge, etc
└── workers/       # Background document indexer
```

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

## License

MIT
