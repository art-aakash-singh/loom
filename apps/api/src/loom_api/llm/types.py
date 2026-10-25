from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["user", "assistant"]

StopReason = Literal["max_tokens", "complete", "refusal"]

ErrorKind = Literal[
    "rate_limited",
    "invalid_request",
    "auth_failed",
    "overloaded",
    "unexpected",
    "refusal",
]

RETRYABLE: frozenset[ErrorKind] = frozenset({"rate_limited", "overloaded"})


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class MessageEnd:
    stop_reason: StopReason
    usage: Usage


@dataclass(frozen=True)
class StreamError:
    kind: ErrorKind
    message: str


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


StreamEvent = TextDelta | MessageEnd | StreamError


class GenerationSettings(Protocol):
    """What a provider needs per request. Read-only, so any frozen settings object fits."""

    @property
    def model(self) -> str: ...

    @property
    def max_output_tokens(self) -> int: ...
