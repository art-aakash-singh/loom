import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.types import ASGIApp, Message, Scope


def parse_sse(body: str) -> list[dict[str, Any]]:
    frames = [f for f in body.split("\n\n") if f]
    assert all(f.startswith("data: ") for f in frames)
    return [json.loads(f.removeprefix("data: ")) for f in frames]


async def eventually(check: Callable[[], Awaitable[bool]], timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if await check():
            return True
        await asyncio.sleep(0.02)
    return await check()


async def post_then_disconnect(
    app: ASGIApp, path: str, payload: dict[str, Any], *, after_chunks: int
) -> int:
    """POST to the app, then hang up after `after_chunks` body chunks. Returns chunks seen.

    Speaks raw ASGI with spec_version 2.3, which is what uvicorn advertises, so Starlette
    takes the same disconnect path (task group + cancel scope) as in production.
    """
    body = json.dumps(payload).encode()
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("testclient", 1234),
        "server": ("test", 80),
    }
    hang_up = asyncio.Event()
    request_sent = False
    chunks = 0

    async def receive() -> Message:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await hang_up.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        nonlocal chunks
        if message["type"] == "http.response.body" and message.get("body"):
            chunks += 1
            if chunks >= after_chunks:
                hang_up.set()

    await app(scope, receive, send)
    return chunks
