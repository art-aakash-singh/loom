from collections.abc import AsyncGenerator, Sequence
from typing import Protocol

from loom_api.llm.types import GenerationSettings, Message, StreamEvent


class LLMProvider(Protocol):
    def stream(
        self,
        system: str,
        messages: Sequence[Message],
        settings: GenerationSettings,
    ) -> AsyncGenerator[StreamEvent]: ...

    def estimate_tokens(self, text: str) -> int:
        """Token count of `text` for this provider's model, without calling it."""
        ...
