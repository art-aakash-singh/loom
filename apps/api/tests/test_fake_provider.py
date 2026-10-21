from loom_api.chat.schemas import ConcreteGenerationSettings
from loom_api.llm.fake import FakeProvider
from loom_api.llm.types import (
    GenerationSettings,
    Message,
    MessageEnd,
    StreamError,
    StreamEvent,
    TextDelta,
)

SETTINGS: GenerationSettings = ConcreteGenerationSettings(model="fake", max_tokens=100)
FULL_REPLY = "Hello from the fake provider. This is a streamed reply."


async def collect(provider: FakeProvider) -> list[StreamEvent]:
    return [e async for e in provider.stream("sys", [Message("user", "hi")], SETTINGS)]


async def test_joined_deltas_equal_full_reply() -> None:
    events = await collect(FakeProvider())

    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert text == FULL_REPLY


async def test_stream_ends_with_exactly_one_message_end() -> None:
    events = await collect(FakeProvider())

    assert isinstance(events[-1], MessageEnd)
    assert sum(isinstance(e, MessageEnd) for e in events) == 1
    assert events[-1].stop_reason == "complete"


async def test_fail_with_yields_deltas_then_one_error() -> None:
    events = await collect(FakeProvider(fail_with="rate_limited"))

    assert isinstance(events[-1], StreamError)
    assert events[-1].kind == "rate_limited"
    assert sum(isinstance(e, StreamError) for e in events) == 1
    assert not any(isinstance(e, MessageEnd) for e in events)
    assert all(isinstance(e, TextDelta) for e in events[:-1])
    assert len(events) > 1
