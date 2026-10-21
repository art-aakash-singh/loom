from collections.abc import AsyncGenerator

from loom_api.chat.schemas import (
    ChatEvent,
    ErrorEvent,
    MessageEndEvent,
    TextDeltaEvent,
    UsageOut,
)
from loom_api.llm.base import LLMProvider
from loom_api.llm.types import (
    RETRYABLE,
    GenerationSettings,
    Message,
    MessageEnd,
    StreamError,
    TextDelta,
)

SYSTEM_PROMPT = "You are Loom, a concise and helpful assistant."


async def stream_reply(
    provider: LLMProvider, settings: GenerationSettings, message: str
) -> AsyncGenerator[ChatEvent]:
    """Stateless single-turn chat: one user message in, domain events out."""
    async for event in provider.stream(SYSTEM_PROMPT, [Message("user", message)], settings):
        match event:
            case TextDelta(text=text):
                yield TextDeltaEvent(text=text)
            case MessageEnd(stop_reason=reason, usage=usage):
                yield MessageEndEvent(
                    stop_reason=reason,
                    usage=UsageOut(
                        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
                    ),
                )
            case StreamError(kind=kind, message=msg):
                yield ErrorEvent(kind=kind, message=msg, retryable=kind in RETRYABLE)
