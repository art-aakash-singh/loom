from typing import Annotated

from fastapi import Depends, Request

from loom_api.chat.service import ChatService
from loom_api.config import Settings
from loom_api.llm.anthropic import AnthropicProvider
from loom_api.llm.base import LLMProvider
from loom_api.llm.fake import FakeProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        # Settings validation guarantees the key is present.
        assert settings.anthropic_api_key is not None
        return AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value())
    return FakeProvider(fail_with=settings.fake_fail_with, delay_s=settings.fake_delay_s)


def get_chat_service(request: Request) -> ChatService:
    chat_service: ChatService = request.app.state.chat_service
    return chat_service


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
