from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from loom_api.chat.errors import ConversationNotFound
from loom_api.chat.models import ConversationRow, MessageRow
from loom_api.chat.records import (
    ContentBlock,
    ConversationRecord,
    FinalStatus,
    MessageRecord,
    MessageRef,
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
        token_count=row.token_count,
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


async def _message_refs(session: AsyncSession, conversation_id: UUID) -> list[MessageRef]:
    rows = await session.execute(
        select(MessageRow.id, MessageRow.parent_id, MessageRow.created_at)
        .where(MessageRow.conversation_id == conversation_id)
        .order_by(MessageRow.created_at, MessageRow.id)
    )
    return [MessageRef(id=r.id, parent_id=r.parent_id, created_at=r.created_at) for r in rows]


class LockedConversation:
    """A conversation row held FOR UPDATE until the `async with repo.locked(...)` block exits.

    Everything done through it commits together at the end of that block. The service
    decides what to insert; this class only knows how.
    """

    def __init__(self, session: AsyncSession, row: ConversationRow) -> None:
        self._session = session
        self._row = row

    @property
    def current_leaf_id(self) -> UUID | None:
        return self._row.current_leaf_id

    async def get_message(self, message_id: UUID) -> MessageRecord | None:
        row = await self._session.scalar(
            select(MessageRow).where(
                MessageRow.conversation_id == self._row.id, MessageRow.id == message_id
            )
        )
        return _to_message(row) if row else None

    async def message_refs(self) -> list[MessageRef]:
        return await _message_refs(self._session, self._row.id)

    async def add_user_message(
        self, *, parent_id: UUID | None, text_: str, token_count: int
    ) -> MessageRecord:
        now = datetime.now(UTC)
        return await self._add(
            MessageRow(
                id=uuid4(),
                conversation_id=self._row.id,
                parent_id=parent_id,
                role="user",
                status="complete",
                content=[{"type": "text", "text": text_}],
                token_count=token_count,
                created_at=now,
                finished_at=now,
            )
        )

    async def add_streaming_reply(self, *, parent_id: UUID, model: str) -> MessageRecord:
        return await self._add(
            MessageRow(
                id=uuid4(),
                conversation_id=self._row.id,
                parent_id=parent_id,
                role="assistant",
                status="streaming",
                content=[],
                model=model,
                created_at=datetime.now(UTC),
            )
        )

    def set_leaf(self, message_id: UUID) -> None:
        self._row.current_leaf_id = message_id

    async def _add(self, row: MessageRow) -> MessageRecord:
        self._session.add(row)
        # Flush now: no ORM relationship is mapped, so the unit of work cannot know that a
        # later row's parent_id points at this one and must be inserted first.
        await self._session.flush()
        self._row.updated_at = func.now()
        return _to_message(row)


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
        """Most recently active first (a new message bumps updated_at)."""
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

    async def message_refs(self, conversation_id: UUID) -> list[MessageRef]:
        """Every message's place in the tree, oldest first."""
        async with self._session_factory() as session:
            return await _message_refs(session, conversation_id)

    @asynccontextmanager
    async def locked(self, conversation_id: UUID) -> AsyncIterator[LockedConversation]:
        """Lock the conversation row FOR UPDATE for the block; commit when it exits.

        Concurrent writers to the same conversation queue here, so each one sees the
        previous one's current_leaf_id instead of both branching off the same message.
        """
        async with self._session_factory.begin() as session:
            row = await session.scalar(
                select(ConversationRow)
                .where(ConversationRow.id == conversation_id)
                .with_for_update()
            )
            if row is None:
                raise ConversationNotFound(str(conversation_id))
            yield LockedConversation(session, row)

    async def finalize_assistant(
        self,
        message_id: UUID,
        *,
        status: FinalStatus,
        content: list[ContentBlock],
        stop_reason: StopReason | None,
        error_kind: ErrorKind | None,
        usage: Usage | None,
        token_count: int,
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
                    token_count=token_count,
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
                # Content is only written at finalize, so a stuck row has none: 0 tokens.
                .values(
                    status="error", error_kind="unexpected", token_count=0, finished_at=func.now()
                )
            )
            return cast(CursorResult[Any], result).rowcount
