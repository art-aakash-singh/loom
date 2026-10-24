from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, func, select, text, update

from loom_api.chat.errors import ConversationNotFound
from loom_api.chat.models import ConversationRow, MessageRow
from loom_api.chat.records import (
    ContentBlock,
    ConversationRecord,
    FinalStatus,
    MessageRecord,
    MessageStatus,
)
from loom_api.db import SessionFactory
from loom_api.llm.types import ErrorKind, Role, StopReason, Usage

# Walks parent links upward from one message; `depth` counts away from it, so ordering by
# depth DESC gives root-first. Parent links never change, so the path to a given message
# is stable even while new turns are appended after it.
_PATH_TO_SQL = text(
    """
    WITH RECURSIVE path AS (
        SELECT m.*, 0 AS depth
        FROM messages m
        WHERE m.id = :message_id
      UNION ALL
        SELECT m.*, p.depth + 1
        FROM messages m
        JOIN path p ON m.id = p.parent_id
    )
    SELECT * FROM path ORDER BY depth DESC
    """
)


def _to_message(row: MessageRow) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        parent_id=row.parent_id,
        role=cast(Role, row.role),
        status=cast(MessageStatus, row.status),
        content=cast(list[ContentBlock], row.content),
        stop_reason=cast(StopReason | None, row.stop_reason),
        error_kind=cast(ErrorKind | None, row.error_kind),
        model=row.model,
        usage=Usage(**row.usage) if row.usage else None,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


def _to_conversation(row: ConversationRow) -> ConversationRecord:
    return ConversationRecord(
        id=row.id,
        title=row.title,
        current_leaf_id=row.current_leaf_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ChatRepository:
    """The only place that talks to Postgres for the chat domain.

    Every method opens its own session and transaction from the factory. Nothing is
    request-scoped, so the shielded write in a stream's `finally` cannot hit a session
    that the framework already closed.
    """

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def create_conversation(self, title: str | None = None) -> ConversationRecord:
        async with self._session_factory.begin() as session:
            row = ConversationRow(id=uuid4(), title=title)
            session.add(row)
            await session.flush()
            await session.refresh(row)  # pull server-side defaults (created_at, updated_at)
            return _to_conversation(row)

    async def get_conversation(self, conversation_id: UUID) -> ConversationRecord | None:
        async with self._session_factory() as session:
            row = await session.get(ConversationRow, conversation_id)
            return _to_conversation(row) if row else None

    async def list_conversations(self, limit: int) -> list[ConversationRecord]:
        """Most recently active first (a new turn bumps updated_at)."""
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(ConversationRow)
                .order_by(ConversationRow.updated_at.desc(), ConversationRow.id)
                .limit(limit)
            )
            return [_to_conversation(row) for row in rows]

    async def path_to(self, message_id: UUID) -> list[MessageRecord]:
        """The messages from the root down to `message_id`, root-first."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(MessageRow).from_statement(_PATH_TO_SQL), {"message_id": message_id}
            )
            return [_to_message(row) for row in result.scalars()]

    async def start_turn(
        self, conversation_id: UUID, text_: str, *, model: str
    ) -> tuple[MessageRecord, MessageRecord]:
        """Append a user message and an empty 'streaming' reply under the current leaf.

        The conversation row is locked FOR UPDATE, so two turns started at once queue here
        and the second one chains onto the first one's reply instead of branching.
        """
        now = datetime.now(UTC)
        async with self._session_factory.begin() as session:
            conversation = await session.scalar(
                select(ConversationRow)
                .where(ConversationRow.id == conversation_id)
                .with_for_update()
            )
            if conversation is None:
                raise ConversationNotFound(str(conversation_id))

            user = MessageRow(
                id=uuid4(),
                conversation_id=conversation_id,
                parent_id=conversation.current_leaf_id,
                role="user",
                status="complete",
                content=[{"type": "text", "text": text_}],
                created_at=now,
                finished_at=now,
            )
            session.add(user)
            # Flush before adding the reply: the unit of work doesn't know the reply's
            # parent_id points at this row, so it must already be in the table.
            await session.flush()
            assistant = MessageRow(
                id=uuid4(),
                conversation_id=conversation_id,
                parent_id=user.id,
                role="assistant",
                status="streaming",
                content=[],
                model=model,
                created_at=now,
            )
            session.add(assistant)
            await session.flush()

            conversation.current_leaf_id = assistant.id
            conversation.updated_at = func.now()
            return _to_message(user), _to_message(assistant)

    async def finalize_assistant(
        self,
        message_id: UUID,
        *,
        status: FinalStatus,
        content: list[ContentBlock],
        stop_reason: StopReason | None,
        error_kind: ErrorKind | None,
        usage: Usage | None,
    ) -> bool:
        """Write the outcome of a streaming reply. False if it was no longer streaming.

        The status guard keeps a late finalize from overwriting a row the startup sweep has
        already closed, and makes a second finalize of the same row a no-op.
        """
        async with self._session_factory.begin() as session:
            result = await session.execute(
                update(MessageRow)
                .where(MessageRow.id == message_id, MessageRow.status == "streaming")
                .values(
                    status=status,
                    content=content,
                    stop_reason=stop_reason,
                    error_kind=error_kind,
                    usage=asdict(usage) if usage else None,
                    finished_at=func.now(),
                )
            )
            return cast(CursorResult[Any], result).rowcount == 1

    async def fail_streaming_messages(self) -> int:
        """Close every 'streaming' row as error/unexpected. Returns how many there were."""
        async with self._session_factory.begin() as session:
            result = await session.execute(
                update(MessageRow)
                .where(MessageRow.status == "streaming")
                .values(status="error", error_kind="unexpected", finished_at=func.now())
            )
            return cast(CursorResult[Any], result).rowcount
