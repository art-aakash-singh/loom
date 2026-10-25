from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from loom_api.llm.types import ErrorKind


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LOOM_", env_ignore_empty=True, extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://loom:loom@localhost:5433/loom"
    redis_url: str = "redis://localhost:6380/0"
    # Integration tests truncate tables and flush Redis: keep them off the dev data.
    test_database_url: str = "postgresql+asyncpg://loom:loom@localhost:5433/loom_test"
    test_redis_url: str = "redis://localhost:6380/15"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Safety net only: the lock is released explicitly when a generation ends.
    generation_lock_ttl_s: int = Field(default=300, gt=0)

    llm_provider: Literal["fake", "anthropic"] = "fake"
    anthropic_api_key: SecretStr | None = None
    fake_fail_with: ErrorKind | None = None
    fake_delay_s: float = Field(default=0.05, ge=0)
    llm_model: str = "claude-sonnet-5-5"
    llm_max_tokens: int = 1024
    # Input + output tokens per model. LOOM_LLM_CONTEXT_WINDOWS='{"model": n}' overrides it,
    # e.g. a tiny window to exercise the too-large path with the fake provider.
    llm_context_windows: dict[str, int] = {
        "claude-sonnet-5-5": 1_000_000,
        "claude-opus-5-5": 1_000_000,
        "claude-haiku-5-5": 1_000_000,
    }

    @model_validator(mode="after")
    def _require_key_for_anthropic(self) -> Self:
        if self.llm_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("LOOM_ANTHROPIC_API_KEY is required when LOOM_LLM_PROVIDER=anthropic")
        return self

    @model_validator(mode="after")
    def _require_context_window_for_model(self) -> Self:
        if self.llm_model not in self.llm_context_windows:
            raise ValueError(
                f"No context window configured for LOOM_LLM_MODEL={self.llm_model!r}; "
                "add it to LOOM_LLM_CONTEXT_WINDOWS"
            )
        return self

    @property
    def context_window(self) -> int:
        return self.llm_context_windows[self.llm_model]


settings = Settings()
