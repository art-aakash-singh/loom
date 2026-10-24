from datetime import UTC, datetime
from uuid import uuid4

from loom_api.chat.context import build_context
from loom_api.chat.records import ContentBlock, MessageRecord, MessageStatus
from loom_api.llm.types import Message, Role


def record(role: Role, status: MessageStatus, text: str | None) -> MessageRecord:
    content: list[ContentBlock] = [] if text is None else [{"type": "text", "text": text}]
    now = datetime.now(UTC)
    return MessageRecord(
        id=uuid4(),
        conversation_id=uuid4(),
        parent_id=None,
        role=role,
        status=status,
        content=content,
        stop_reason=None,
        error_kind=None,
        model=None,
        usage=None,
        created_at=now,
        finished_at=now,
    )


def test_keeps_everything_including_partial_replies() -> None:
    chain = [
        record("user", "complete", "q1"),
        record("assistant", "cancelled", "partial"),
        record("user", "complete", "q2"),
    ]

    assert build_context(chain) == [
        Message("user", "q1"),
        Message("assistant", "partial"),
        Message("user", "q2"),
    ]


def test_drops_assistant_messages_with_no_content() -> None:
    chain = [record("user", "complete", "q1"), record("assistant", "error", None)]

    assert build_context(chain) == [Message("user", "q1")]
