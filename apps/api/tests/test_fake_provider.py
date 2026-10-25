from loom_api.context.types import GenerationSettings as Settings
from loom_api.llm.fake import FakeProvider
from loom_api.llm.types import (
    GenerationSettings,
    Message,
    MessageEnd,
    StreamError,
    StreamEvent,
    TextDelta,
)

SETTINGS: GenerationSettings = Settings(model="fake", max_output_tokens=100, context_window=1000)


async def collect(provider: FakeProvider) -> list[StreamEvent]:
    return [e async for e in provider.stream("sys", [Message("user", "hi")], SETTINGS)]


async def test_deltas_join_into_cleanly_spaced_text() -> None:
    events = await collect(FakeProvider(delay_s=0))

    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert text
    assert text == text.lstrip()  # no separator before the first word
    assert "  " not in text.replace("\n\n", "")  # one space between words


def test_estimate_is_a_quarter_of_the_characters_rounded_up() -> None:
    provider = FakeProvider()

    assert [provider.estimate_tokens(t) for t in ("", "abc", "abcd", "abcde")] == [0, 1, 1, 2]


async def test_stream_ends_with_exactly_one_message_end() -> None:
    events = await collect(FakeProvider(delay_s=0))

    assert isinstance(events[-1], MessageEnd)
    assert sum(isinstance(e, MessageEnd) for e in events) == 1
    assert events[-1].stop_reason == "complete"


async def test_fail_with_yields_deltas_then_one_error() -> None:
    events = await collect(FakeProvider(fail_with="rate_limited", delay_s=0))

    assert isinstance(events[-1], StreamError)
    assert events[-1].kind == "rate_limited"
    assert sum(isinstance(e, StreamError) for e in events) == 1
    assert not any(isinstance(e, MessageEnd) for e in events)
    assert all(isinstance(e, TextDelta) for e in events[:-1])
    assert len(events) > 1
