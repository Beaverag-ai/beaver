FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

# Clone and install telegram-mcp
RUN git clone https://github.com/chigwell/telegram-mcp.git /opt/telegram-mcp \
    && cd /opt/telegram-mcp && uv sync

# Install SSE bridge dependencies
COPY docker/telegram-mcp-bridge.py /app/bridge.py
RUN uv pip install --system starlette uvicorn mcp httpx

EXPOSE 3001

# The bridge script launches telegram-mcp as a subprocess (stdio)
# and exposes it over SSE for the Beaver API to connect to
CMD ["python", "/app/bridge.py"]
