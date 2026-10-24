import asyncio
from collections.abc import AsyncGenerator, Sequence

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
    def __init__(self, fail_with: ErrorKind | None = None, delay_s: float = 0.1):
        self.fail_with = fail_with
        self.delay_s = delay_s

    async def stream(
        self, system: str, messages: Sequence[Message], settings: GenerationSettings
    ) -> AsyncGenerator[StreamEvent]:

        fake_res = """Thank you for sharing this. After carefully reviewing your message and considering the context, I can provide a more detailed explanation of the situation.

Based on my analysis, your approach appears to be reasonable, and there are several aspects worth acknowledging. However, it is important to consider that the outcome may depend on a number of factors that are not immediately apparent from the information provided.

First, I would like to clarify that while your initial understanding is not necessarily incorrect, there may be alternative interpretations that are equally valid depending on the circumstances. In situations like this, it is generally advisable to examine the available information from multiple perspectives before reaching a definitive conclusion.

Second, although the reasoning presented appears consistent at first glance, certain assumptions may require further examination. This does not automatically mean that the conclusion is incorrect; rather, it suggests that a more comprehensive evaluation could help establish whether the reasoning holds up under different conditions.

Additionally, it is worth noting that context plays a significant role in determining the most appropriate interpretation. Information that seems straightforward in isolation can sometimes have a different meaning when considered alongside other relevant details.

Ultimately, my recommendation would be to approach this matter with a balanced perspective, take the relevant factors into account, and avoid drawing conclusions prematurely. A careful and methodical approach will generally lead to a clearer understanding of the situation.

I hope this provides a more comprehensive explanation. If you would like, I can also elaborate on any particular aspect, explore alternative interpretations, or provide a more detailed breakdown of the reasoning involved.

Please let me know if you need any further clarification. I'm happy to help. """

        output_tokens: int = len(fake_res) // 3
        fail_at = 4

        for index, word in enumerate(fake_res.split(" ")):
            await asyncio.sleep(self.delay_s)

            if self.fail_with is not None and index == fail_at:
                yield StreamError(self.fail_with, f"Simulated {self.fail_with} error")
                return

            yield TextDelta(text=word if index == 0 else " " + word)

        yield MessageEnd("complete", Usage(40, output_tokens))
        return
