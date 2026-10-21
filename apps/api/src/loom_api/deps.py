from typing import Annotated

from fastapi import Depends, Request

from loom_api.config import Settings
from loom_api.llm.anthropic import AnthropicProvider
from loom_api.llm.base import LLMProvider
from loom_api.llm.fake import FakeProvider
from loom_api.llm.types import GenerationSettings


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        # Settings validation guarantees the key is present.
        assert settings.anthropic_api_key is not None
        return AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value())
    return FakeProvider(fail_with=settings.fake_fail_with)


def get_provider(request: Request) -> LLMProvider:
    provider: LLMProvider = request.app.state.provider
    return provider


def get_generation_settings(request: Request) -> GenerationSettings:
    generation_settings: GenerationSettings = request.app.state.generation_settings
    return generation_settings


ProviderDep = Annotated[LLMProvider, Depends(get_provider)]
GenerationSettingsDep = Annotated[GenerationSettings, Depends(get_generation_settings)]
