from __future__ import annotations

import pytest

from proresponse.core import RewriteService, rewrite
from proresponse.providers import ProviderError
from tests.fakes import FakeProvider


def make_service(**kwargs) -> tuple[RewriteService, FakeProvider]:
    provider = FakeProvider(**kwargs)
    service = RewriteService(provider=provider, model="test-model")
    return service, provider


def test_rewrite_returns_provider_result():
    service, provider = make_service()
    result = service.rewrite("hey can u fix teh report", transform="professional")
    assert result.text == "REWRITTEN"
    assert result.model == "test-model"
    assert len(provider.requests) == 1


def test_rewrite_sanitizes_and_builds_prompt():
    service, provider = make_service()
    service.rewrite("hi <@U1|bob>   there", transform="friendly")
    req = provider.requests[0]
    assert "bob" in req.text
    assert "   " not in req.text  # collapsed whitespace
    assert "warm" in req.system_prompt.lower()


def test_model_override_per_call():
    service, provider = make_service()
    service.rewrite("please improve this text", transform="grammar", model="other")
    assert provider.requests[0].model == "other"


def test_too_short_input_raises():
    service, _ = make_service()
    with pytest.raises(ValueError):
        service.rewrite("hi", transform="professional")


def test_provider_error_propagates():
    service, _ = make_service(raise_error=True)
    with pytest.raises(ProviderError):
        service.rewrite("this is long enough to rewrite", transform="professional")


def test_translate_passes_argument():
    service, provider = make_service()
    service.rewrite("good morning everyone", transform="translate", argument="French")
    assert "French" in provider.requests[0].system_prompt


def test_module_level_rewrite_helper():
    provider = FakeProvider(reply="OK")
    result = rewrite(
        "make this much nicer please",
        provider=provider,
        model="m",
        transform="concise",
    )
    assert result.text == "OK"
