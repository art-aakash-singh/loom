from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from loom_api.llm.types import ErrorKind


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LOOM_", env_ignore_empty=True, extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://loom:loom@localhost:5432/loom"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]

    llm_provider: Literal["fake", "anthropic"] = "fake"
    anthropic_api_key: SecretStr | None = None
    fake_fail_with: ErrorKind | None = None
    llm_model: str = "claude-sonnet-5-5"
    llm_max_tokens: int = 1024

    @model_validator(mode="after")
    def _require_key_for_anthropic(self) -> Self:
        if self.llm_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("LOOM_ANTHROPIC_API_KEY is required when LOOM_LLM_PROVIDER=anthropic")
        return self


settings = Settings()
