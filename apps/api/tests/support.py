import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from loom_api.context.types import ContextInput, ProviderRequest
from loom_api.llm import types as llm
from starlette.types import ASGIApp, Message, Scope


def passthrough_build(inp: ContextInput) -> ProviderRequest:
    """Test stand-in for context.build: the whole path, no budgeting.

    Drops messages without content (a reply that failed before its first token), since a
    provider rejects empty turns. Nothing else is filtered.
    """
    messages = tuple(
        llm.Message(m.role, "".join(block["text"] for block in m.content))
        for m in inp.path
        if m.content
    )
    return ProviderRequest(system=inp.system_prompt, messages=messages, settings=inp.settings)


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


# --- Chat API helpers shared by the integration tests ----------------------------------

from collections.abc import AsyncGenerator, Sequence  # noqa: E402
from uuid import UUID  # noqa: E402

from httpx import AsyncClient  # noqa: E402
from loom_api.chat.lock import lock_key  # noqa: E402
from loom_api.chat.records import MessageRecord  # noqa: E402
from loom_api.chat.repository import ChatRepository  # noqa: E402
from loom_api.llm.estimate import estimate_tokens_by_chars  # noqa: E402
from loom_api.llm.fake import FakeProvider  # noqa: E402
from redis.asyncio import Redis  # noqa: E402


def _fake_reply() -> str:
    async def collect() -> str:
        events = FakeProvider(delay_s=0).stream("", [], None)  # type: ignore[arg-type]
        return "".join([e.text async for e in events if isinstance(e, llm.TextDelta)])

    return asyncio.run(collect())


# Whatever FakeProvider currently says, so tests don't break when its canned text changes.
FULL_REPLY = _fake_reply()
# FakeProvider(fail_with=...) fails after its first 4 words.
PARTIAL_REPLY = " ".join(FULL_REPLY.split(" ")[:4])


class ScriptedProvider:
    def __init__(self, *events: llm.StreamEvent) -> None:
        self._events = events
        self.seen: list[Sequence[llm.Message]] = []

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens_by_chars(text)

    async def stream(
        self, system: str, messages: Sequence[llm.Message], settings: llm.GenerationSettings
    ) -> AsyncGenerator[llm.StreamEvent]:
        self.seen.append(messages)
        for event in self._events:
            yield event


class GatedProvider:
    """Emits one delta, then waits until the test lets it finish."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens_by_chars(text)

    async def stream(
        self, system: str, messages: Sequence[llm.Message], settings: llm.GenerationSettings
    ) -> AsyncGenerator[llm.StreamEvent]:
        yield llm.TextDelta("partial")
        self.started.set()
        await self.release.wait()
        yield llm.MessageEnd("complete", llm.Usage(3, 4))


def ok_provider(reply: str = "ok") -> ScriptedProvider:
    return ScriptedProvider(llm.TextDelta(reply), llm.MessageEnd("complete", llm.Usage(1, 7)))


async def create_conversation(client: AsyncClient) -> UUID:
    response = await client.post("/conversations")
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def send(
    client: AsyncClient, cid: UUID, text: str = "hi", **extra: object
) -> tuple[int, str]:
    response = await client.post(f"/conversations/{cid}/messages", json={"text": text, **extra})
    return response.status_code, response.text


async def regenerate(client: AsyncClient, cid: UUID, user_message_id: str) -> tuple[int, str]:
    response = await client.post(f"/conversations/{cid}/messages/{user_message_id}/regenerate")
    return response.status_code, response.text


async def get_conversation(client: AsyncClient, cid: UUID) -> dict[str, Any]:
    response = await client.get(f"/conversations/{cid}")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def get_messages(client: AsyncClient, cid: UUID) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = (await get_conversation(client, cid))["messages"]
    return messages


async def active_path(repo: ChatRepository, cid: UUID) -> list[MessageRecord]:
    conversation = await repo.get_conversation(cid)
    assert conversation is not None
    leaf = conversation.current_leaf_id
    return await repo.path_to(leaf) if leaf else []


async def lock_is_free(redis: Redis, cid: UUID) -> bool:
    return not await redis.exists(lock_key(cid))
