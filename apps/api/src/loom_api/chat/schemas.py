from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from loom_api.chat.records import MessageStatus
from loom_api.llm.types import ErrorKind, Role, StopReason


class CreateConversationRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None

    @field_validator("title")
    @classmethod
    def _blank_is_untitled(cls, title: str | None) -> str | None:
        return title or None


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1)


class UsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    input_tokens: int
    output_tokens: int


class ContentBlockOut(BaseModel):
    type: Literal["text"]
    text: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: UUID | None
    role: Role
    status: MessageStatus
    content: list[ContentBlockOut]
    stop_reason: StopReason | None
    error_kind: ErrorKind | None
    model: str | None
    usage: UsageOut | None
    created_at: datetime
    finished_at: datetime | None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    current_leaf_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class TurnStartedEvent(BaseModel):
    """First event of every stream: the ids of the rows this turn created."""

    type: Literal["turn_started"] = "turn_started"
    user_message_id: UUID
    assistant_message_id: UUID


class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class MessageEndEvent(BaseModel):
    type: Literal["message_end"] = "message_end"
    stop_reason: StopReason
    usage: UsageOut


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    kind: ErrorKind
    message: str
    retryable: bool


ChatEvent = Annotated[
    TurnStartedEvent | TextDeltaEvent | MessageEndEvent | ErrorEvent,
    Field(discriminator="type"),
]


@dataclass(frozen=True)
class ConcreteGenerationSettings:
    model: str
    max_tokens: int
