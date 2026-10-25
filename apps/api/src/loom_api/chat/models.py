"""ORM mapping for the chat tables.

The migrations are the source of truth for constraints and indexes; this mapping only
describes columns so the repository can read and write rows.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from loom_api.db import Base


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    # FK to messages lives in the migration only: declaring it here would make the two
    # tables a cycle in the metadata, which we never use for create_all anyway.
    current_leaf_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "parent_id"],
            ["messages.conversation_id", "messages.id"],
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column()
    parent_id: Mapped[UUID | None] = mapped_column()
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    content: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    token_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
