from __future__ import annotations

from proresponse.providers.registry import (
    DEFAULTS,
    MODELS,
    models_for_provider,
    resolve,
)


def test_resolve_known_model():
    info = resolve("gpt-5-mini")
    assert info is not None
    assert info.provider == "openai"


def test_resolve_unknown_returns_none():
    assert resolve("totally-made-up-model") is None
    assert resolve("") is None


def test_models_for_provider():
    openai_models = models_for_provider("openai")
    assert openai_models
    assert all(m.provider == "openai" for m in openai_models)
    anthropic_models = models_for_provider("anthropic")
    assert any(m.id == "claude-opus-4-8" for m in anthropic_models)


def test_defaults_cover_providers():
    for provider in ("openai", "anthropic", "openai-compatible"):
        assert provider in DEFAULTS
        assert DEFAULTS[provider]


def test_reasoning_flag_present_for_gpt5():
    info = resolve("gpt-5")
    assert info is not None and info.reasoning is True


def test_registry_ids_unique():
    ids = [m.id for m in MODELS]
    assert len(ids) == len(set(ids))
