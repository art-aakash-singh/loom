from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from loom_api.llm.types import ErrorKind, StopReason


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


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
    TextDeltaEvent | MessageEndEvent | ErrorEvent,
    Field(discriminator="type"),
]


@dataclass(frozen=True)
class ConcreteGenerationSettings:
    model: str
    max_tokens: int
