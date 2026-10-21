from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from loom_api.llm.types import GenerationSettings, Message, StreamEvent


class LLMProvider(Protocol):
    def stream(
        self,
        system: str,
        messages: Sequence[Message],
        settings: GenerationSettings,
    ) -> AsyncIterator[StreamEvent]: ...
