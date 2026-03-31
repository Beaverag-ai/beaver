"""SSE bridge for telegram-mcp.

Launches telegram-mcp as a stdio subprocess and exposes it via SSE
so the Beaver API container can connect to it over the network.

The MCP stdio protocol uses newline-delimited JSON (one JSON object per line).
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram-mcp-bridge")

# Global state for the subprocess
process: asyncio.subprocess.Process | None = None
pending_requests: dict[str, asyncio.Future] = {}
sse_clients: list[asyncio.Queue] = []


async def start_telegram_mcp():
    """Start telegram-mcp as a subprocess."""
    global process
    env = os.environ.copy()
    cmd = ["uv", "--directory", "/opt/telegram-mcp", "run", "main.py"]
    log.info(f"Starting telegram-mcp: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    asyncio.create_task(_read_stderr())
    log.info("telegram-mcp started")


async def _read_stderr():
    """Log stderr from the subprocess."""
    if not process or not process.stderr:
        return
    while True:
        line = await process.stderr.readline()
        if not line:
            break
        log.warning(f"[telegram-mcp] {line.decode().rstrip()}")


async def send_to_mcp(request_data: dict) -> dict:
    """Send a JSON-RPC request to the subprocess via newline-delimited JSON."""
    if not process or not process.stdin or not process.stdout:
        return {"error": "telegram-mcp not running"}

    req_id = request_data.get("id", str(uuid4()))
    request_data["id"] = req_id

    payload = json.dumps(request_data) + "\n"

    future: asyncio.Future = asyncio.get_event_loop().create_future()
    pending_requests[req_id] = future

    process.stdin.write(payload.encode())
    await process.stdin.drain()

    try:
        result = await asyncio.wait_for(future, timeout=60)
        return result
    except asyncio.TimeoutError:
        pending_requests.pop(req_id, None)
        return {"error": "timeout"}


async def read_responses():
    """Continuously read newline-delimited JSON responses from subprocess stdout."""
    if not process or not process.stdout:
        return

    while True:
        try:
            line = await process.stdout.readline()
            if not line:
                log.warning("telegram-mcp subprocess stdout closed")
                break

            line = line.decode().strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                log.error(f"Invalid JSON from subprocess: {line[:200]}")
                continue

            req_id = msg.get("id")
            if req_id and str(req_id) in pending_requests:
                pending_requests.pop(str(req_id)).set_result(msg)
            elif req_id is not None and str(req_id) in pending_requests:
                pending_requests.pop(str(req_id)).set_result(msg)
            else:
                # Notification — broadcast to SSE clients
                for q in sse_clients:
                    await q.put(msg)

        except Exception as e:
            log.error(f"Error reading from subprocess: {e}")
            break


# ── SSE Endpoint ──

async def sse_endpoint(request: Request):
    """SSE endpoint that forwards MCP protocol messages."""
    queue: asyncio.Queue = asyncio.Queue()
    sse_clients.append(queue)

    async def event_generator():
        try:
            yield f"event: endpoint\ndata: /message\n\n"
            while True:
                msg = await queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def message_endpoint(request: Request):
    """Handle incoming MCP JSON-RPC messages and forward to subprocess."""
    try:
        body = await request.json()
        result = await send_to_mcp(body)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def health_endpoint(request: Request):
    alive = process is not None and process.returncode is None
    return JSONResponse({"status": "ok" if alive else "down"})


# ── App ──


@asynccontextmanager
async def lifespan(app):
    await start_telegram_mcp()
    asyncio.create_task(read_responses())
    yield
    if process:
        process.terminate()
        await process.wait()


app = Starlette(
    routes=[
        Route("/sse", sse_endpoint),
        Route("/message", message_endpoint, methods=["POST"]),
        Route("/health", health_endpoint),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
