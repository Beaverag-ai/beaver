"""SSE bridge for telegram-mcp.

Launches telegram-mcp as a stdio subprocess and exposes it via SSE
so the Beaver API container can connect to it over the network.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from uuid import uuid4

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram-mcp-bridge")

# Global state for the subprocess
process: asyncio.subprocess.Process | None = None
pending_requests: dict[str, asyncio.Future] = {}
sse_clients: list[asyncio.Queue] = []
read_lock = asyncio.Lock()


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
    # Start reading stderr in background
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
    """Send a JSON-RPC request to the subprocess and wait for response."""
    if not process or not process.stdin or not process.stdout:
        return {"error": "telegram-mcp not running"}

    req_id = request_data.get("id", str(uuid4()))
    request_data["id"] = req_id

    payload = json.dumps(request_data)
    message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"

    future: asyncio.Future = asyncio.get_event_loop().create_future()
    pending_requests[req_id] = future

    process.stdin.write(message.encode())
    await process.stdin.drain()

    try:
        result = await asyncio.wait_for(future, timeout=60)
        return result
    except asyncio.TimeoutError:
        pending_requests.pop(req_id, None)
        return {"error": "timeout"}


async def read_responses():
    """Continuously read JSON-RPC responses from the subprocess stdout."""
    if not process or not process.stdout:
        return

    buffer = b""
    while True:
        try:
            chunk = await process.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk

            # Parse Content-Length header based messages
            while b"\r\n\r\n" in buffer:
                header_end = buffer.index(b"\r\n\r\n")
                header = buffer[:header_end].decode()
                content_length = 0
                for line in header.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":")[1].strip())

                total_needed = header_end + 4 + content_length
                if len(buffer) < total_needed:
                    break  # wait for more data

                body = buffer[header_end + 4:total_needed].decode()
                buffer = buffer[total_needed:]

                try:
                    msg = json.loads(body)
                    req_id = msg.get("id")
                    if req_id and req_id in pending_requests:
                        pending_requests.pop(req_id).set_result(msg)
                    else:
                        # Notification — broadcast to SSE clients
                        for q in sse_clients:
                            await q.put(msg)
                except json.JSONDecodeError:
                    log.error(f"Invalid JSON from subprocess: {body[:100]}")
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
            # Send initial connection event
            yield f"event: endpoint\ndata: /message\n\n"
            while True:
                msg = await queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_clients.remove(queue)

    from starlette.responses import StreamingResponse
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

app = Starlette(
    routes=[
        Route("/sse", sse_endpoint),
        Route("/message", message_endpoint, methods=["POST"]),
        Route("/health", health_endpoint),
    ],
)


@app.on_event("startup")
async def startup():
    await start_telegram_mcp()
    asyncio.create_task(read_responses())


@app.on_event("shutdown")
async def shutdown():
    if process:
        process.terminate()
        await process.wait()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
