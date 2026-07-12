from __future__ import annotations

from proresponse.config import Settings


def test_defaults_resolve_model(monkeypatch):
    monkeypatch.delenv("PRO_MODEL", raising=False)
    monkeypatch.delenv("PRO_PROVIDER", raising=False)
    settings = Settings.from_env(load_dotenv=False)
    assert settings.provider == "openai"
    assert settings.model  # resolved from DEFAULTS


def test_provider_default_model(monkeypatch):
    monkeypatch.setenv("PRO_PROVIDER", "anthropic")
    monkeypatch.delenv("PRO_MODEL", raising=False)
    settings = Settings.from_env(load_dotenv=False)
    assert settings.provider == "anthropic"
    assert settings.model.startswith("claude")


def test_explicit_model_wins(monkeypatch):
    monkeypatch.setenv("PRO_MODEL", "gpt-4.1")
    settings = Settings.from_env(load_dotenv=False)
    assert settings.model == "gpt-4.1"


def test_legacy_env_names(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    settings = Settings.from_env(load_dotenv=False)
    assert settings.openai_api_key == "sk-test"
    assert settings.slack_bot_token == "xoxb-test"
    assert settings.api_key_for_provider() == "sk-test"


def test_api_key_for_anthropic(monkeypatch):
    monkeypatch.setenv("PRO_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    settings = Settings.from_env(load_dotenv=False)
    assert settings.api_key_for_provider() == "sk-ant"


def test_numeric_env_parsing(monkeypatch):
    monkeypatch.setenv("PRO_TEMPERATURE", "0.7")
    monkeypatch.setenv("PRO_MAX_TOKENS", "512")
    monkeypatch.setenv("PRO_RATE_LIMIT_PER_MINUTE", "5")
    settings = Settings.from_env(load_dotenv=False)
    assert settings.temperature == 0.7
    assert settings.max_output_tokens == 512
    assert settings.rate_limit_per_minute == 5
