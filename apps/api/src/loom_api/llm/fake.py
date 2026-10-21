import asyncio
from collections.abc import AsyncIterator, Sequence

from loom_api.llm.types import (
    ErrorKind,
    GenerationSettings,
    Message,
    MessageEnd,
    StreamError,
    StreamEvent,
    TextDelta,
    Usage,
)


class FakeProvider:
    def __init__(self, fail_with: ErrorKind | None = None):
        self.fail_with = fail_with

    async def stream(
        self, system: str, messages: Sequence[Message], settings: GenerationSettings
    ) -> AsyncIterator[StreamEvent]:

        fake_res = "Hello from the fake provider. This is a streamed reply."

        output_tokens: int = len(fake_res) // 3
        fail_at = 4

        for index, word in enumerate(fake_res.split(" ")):
            await asyncio.sleep(0.05)

            if self.fail_with is not None and index == fail_at:
                yield StreamError(self.fail_with, f"Simulated {self.fail_with} error")
                return

            yield TextDelta(text=word if index == 0 else " " + word)

        yield MessageEnd("complete", Usage(40, output_tokens))
        return
