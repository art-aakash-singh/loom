import logging
from collections.abc import AsyncGenerator, Sequence

import anthropic
from anthropic import AsyncAnthropic

from loom_api.llm.estimate import estimate_tokens_by_chars
from loom_api.llm.types import (
    ErrorKind,
    GenerationSettings,
    Message,
    MessageEnd,
    StopReason,
    StreamError,
    StreamEvent,
    TextDelta,
    Usage,
)

logger = logging.getLogger(__name__)

_STOP_REASONS: dict[str, StopReason] = {
    "end_turn": "complete",
    "stop_sequence": "complete",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
}


def _map_stop_reason(raw: str | None) -> StopReason:
    mapped = _STOP_REASONS.get(raw or "")
    if mapped is None:
        logger.warning("Unknown Anthropic stop_reason %r; treating as complete", raw)
        return "complete"
    return mapped


def _map_status(status_code: int) -> ErrorKind:
    # 529 is Anthropic's non-standard "overloaded"; the SDK surfaces it as a generic
    # InternalServerError, so the status code is the only reliable signal.
    if status_code == 429:
        return "rate_limited"
    if status_code == 529:
        return "overloaded"
    if status_code in (401, 403):
        return "auth_failed"
    if status_code in (400, 422):
        return "invalid_request"
    return "unexpected"


class AnthropicProvider:
    def __init__(self, api_key: str):
        self._client = AsyncAnthropic(api_key=api_key)

    def estimate_tokens(self, text: str) -> int:
        # Planned: the real count from the messages.count_tokens endpoint. That is a network
        # call, so this method (and its callers) will have to become async when it lands.
        return estimate_tokens_by_chars(text)

    async def stream(
        self, system: str, messages: Sequence[Message], settings: GenerationSettings
    ) -> AsyncGenerator[StreamEvent]:
        try:
            async with self._client.messages.stream(
                model=settings.model,
                max_tokens=settings.max_output_tokens,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            ) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text=text)
                final = await stream.get_final_message()
        except anthropic.APIStatusError as e:
            logger.warning("Anthropic API error %s: %s", e.status_code, e.message)
            yield StreamError(_map_status(e.status_code), f"Upstream error ({e.status_code})")
            return
        except Exception:
            # Connection errors, timeouts, malformed streams. CancelledError is a
            # BaseException, so client-disconnect cancellation still propagates.
            logger.exception("Unexpected error while streaming from Anthropic")
            yield StreamError("unexpected", "Unexpected error talking to the model provider")
            return

        yield MessageEnd(
            _map_stop_reason(final.stop_reason),
            Usage(final.usage.input_tokens, final.usage.output_tokens),
        )
