"""Values that cross the gather → build boundary. Plain, frozen, no I/O handles."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from loom_api.chat.records import ContentBlock, MessageStatus
from loom_api.llm.types import Message, Role


@dataclass(frozen=True)
class PathMessage:
    id: UUID
    role: Role
    content: tuple[ContentBlock, ...]
    status: MessageStatus
    token_count: int


@dataclass(frozen=True)
class GenerationSettings:
    model: str
    max_output_tokens: int
    context_window: int


@dataclass(frozen=True)
class ContextInput:
    # Root → the user message being answered. Never contains the reply being generated.
    path: tuple[PathMessage, ...]
    system_prompt: str
    now: datetime  # timezone-aware
    settings: GenerationSettings


@dataclass(frozen=True)
class ProviderRequest:
    system: str
    messages: tuple[Message, ...]
    settings: GenerationSettings


class ContextTooLarge(Exception):
    """Even the smallest context build will send does not fit the model's context window."""
