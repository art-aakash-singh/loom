import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from loom_api.chat import service
from loom_api.chat.router import _sse
from loom_api.chat.schemas import ConcreteGenerationSettings
from loom_api.deps import get_generation_settings, get_provider
from loom_api.llm.base import LLMProvider
from loom_api.llm.fake import FakeProvider
from loom_api.llm.types import GenerationSettings, Message, StreamEvent, TextDelta
from loom_api.main import app


@pytest.fixture
def use_provider() -> Iterator[Any]:
    app.dependency_overrides[get_generation_settings] = lambda: ConcreteGenerationSettings(
        model="fake", max_tokens=100
    )

    def _use(provider: LLMProvider) -> None:
        app.dependency_overrides[get_provider] = lambda: provider

    yield _use
    app.dependency_overrides.clear()


def parse_sse(body: str) -> list[dict[str, Any]]:
    frames = [f for f in body.split("\n\n") if f]
    assert all(f.startswith("data: ") for f in frames)
    return [json.loads(f.removeprefix("data: ")) for f in frames]


async def post_chat(message: str = "hi") -> tuple[int, str, str]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/chat", json={"message": message})
    return r.status_code, r.headers["content-type"], r.text


async def test_chat_emits_deltas_then_one_message_end(use_provider: Any) -> None:
    use_provider(FakeProvider())

    status, content_type, body = await post_chat()
    events = parse_sse(body)

    assert status == 200
    assert content_type.startswith("text/event-stream")
    assert [e["type"] for e in events[:-1]] == ["text_delta"] * (len(events) - 1)
    assert events[-1]["type"] == "message_end"
    assert events[-1]["stop_reason"] == "complete"
    assert "".join(e["text"] for e in events[:-1]) == (
        "Hello from the fake provider. This is a streamed reply."
    )


async def test_chat_failure_emits_deltas_then_one_error(use_provider: Any) -> None:
    use_provider(FakeProvider(fail_with="rate_limited"))

    _, _, body = await post_chat()
    events = parse_sse(body)

    assert [e["type"] for e in events] == ["text_delta"] * 4 + ["error"]
    assert events[-1]["kind"] == "rate_limited"
    assert events[-1]["retryable"] is True


async def test_chat_rejects_empty_message(use_provider: Any) -> None:
    use_provider(FakeProvider())

    status, _, _ = await post_chat("")

    assert status == 422


class _Recording:
    """Provider that streams forever and records whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    async def stream(
        self, system: str, messages: Sequence[Message], settings: GenerationSettings
    ) -> AsyncIterator[StreamEvent]:
        try:
            while True:
                await asyncio.sleep(0.01)
                yield TextDelta("x")
        finally:
            self.closed = True


async def test_cancellation_closes_upstream_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    provider = _Recording()
    settings = ConcreteGenerationSettings(model="fake", max_tokens=100)
    started = asyncio.Event()

    async def consume() -> None:
        async for _ in _sse(service.stream_reply(provider, settings, "hi")):
            started.set()

    with caplog.at_level(logging.INFO, logger="loom_api.chat.router"):
        task = asyncio.create_task(consume())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert provider.closed
    assert "Client disconnected" in caplog.text
