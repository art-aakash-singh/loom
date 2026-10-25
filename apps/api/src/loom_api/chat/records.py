from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

from loom_api.llm.types import ErrorKind, Role, StopReason, Usage

MessageStatus = Literal["streaming", "complete", "error", "cancelled"]
# What a streaming assistant row can be finalized to.
FinalStatus = Literal["complete", "error", "cancelled"]


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str


ContentBlock = TextBlock


@dataclass(frozen=True)
class ConversationRecord:
    id: UUID
    title: str | None
    current_leaf_id: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    id: UUID
    conversation_id: UUID
    parent_id: UUID | None
    role: Role
    status: MessageStatus
    content: list[ContentBlock]
    stop_reason: StopReason | None
    error_kind: ErrorKind | None
    model: str | None
    usage: Usage | None
    token_count: int | None  # None only while streaming
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class MessageRef:
    """Just enough of a message to place it in the tree."""

    id: UUID
    parent_id: UUID | None
    created_at: datetime
