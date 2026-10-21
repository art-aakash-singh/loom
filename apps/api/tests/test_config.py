import pytest
from loom_api.config import Settings
from pydantic import ValidationError


def test_anthropic_provider_without_key_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOOM_ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="LOOM_ANTHROPIC_API_KEY"):
        Settings(_env_file=None, llm_provider="anthropic")


def test_anthropic_provider_with_key_is_ok() -> None:
    s = Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key="k")

    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "k"


def test_fake_is_the_default() -> None:
    assert Settings(_env_file=None).llm_provider == "fake"
