from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from loom_api.chat.records import ContentBlock, MessageStatus
from loom_api.context.build import build
from loom_api.context.types import ContextInput, ContextTooLarge, GenerationSettings, PathMessage
from loom_api.llm.types import Message, Role

SETTINGS = GenerationSettings(model="fake", max_output_tokens=100, context_window=10_000)


def msg(role: Role, text: str, status: MessageStatus = "complete") -> PathMessage:
    content: tuple[ContentBlock, ...] = ({"type": "text", "text": text},) if text else ()
    return PathMessage(
        id=uuid4(), role=role, content=content, status=status, token_count=len(text) // 4 + 1
    )


def context(*path: PathMessage, now: datetime | None = None) -> ContextInput:
    return ContextInput(
        path=path,
        system_prompt="You are Loom.",
        now=now or datetime(2026, 10, 25, 9, 30, tzinfo=UTC),
        settings=SETTINGS,
    )


def test_sends_the_path_as_alternating_messages() -> None:
    request = build(context(msg("user", "hi"), msg("assistant", "hello"), msg("user", "how?")))
    assert request.messages == (
        Message("user", "hi"),
        Message("assistant", "hello"),
        Message("user", "how?"),
    )
    assert request.settings == SETTINGS


def test_system_prompt_carries_the_utc_date_but_not_the_time() -> None:
    late_in_india = datetime(2026, 10, 25, 2, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    request = build(context(msg("user", "hi"), now=late_in_india))
    assert request.system == "You are Loom.\n\nToday's date is 2026-10-24."


def test_the_same_day_gives_the_same_system_prompt() -> None:
    morning = build(context(msg("user", "hi"), now=datetime(2026, 10, 25, 1, tzinfo=UTC)))
    night = build(context(msg("user", "hi"), now=datetime(2026, 10, 25, 23, tzinfo=UTC)))
    assert morning.system == night.system


def test_partial_text_from_a_cancelled_or_failed_reply_is_kept() -> None:
    request = build(
        context(
            msg("user", "one"),
            msg("assistant", "half an ans", status="cancelled"),
            msg("user", "two"),
            msg("assistant", "it bro", status="error"),
            msg("user", "three"),
        )
    )
    assert [m.content for m in request.messages] == ["one", "half an ans", "two", "it bro", "three"]


def test_an_empty_failed_reply_is_dropped_and_the_user_messages_around_it_merge() -> None:
    request = build(
        context(msg("user", "hi"), msg("assistant", "", status="error"), msg("user", "again?"))
    )
    assert request.messages == (Message("user", "hi\n\nagain?"),)


def test_context_too_large_propagates() -> None:
    huge = msg("user", "x" * 50_000)
    with pytest.raises(ContextTooLarge):
        build(context(huge))
