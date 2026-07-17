from __future__ import annotations

import json

from proresponse.core import RewriteService
from proresponse.providers.base import LLMProvider
from proresponse.server import process_request
from tests.fakes import FakeProvider


class _BoomProvider(LLMProvider):
    """A provider that raises an unexpected (non-ProviderError) exception."""

    name = "boom"

    def rewrite(self, request):
        raise RuntimeError("kaboom")


def make_service(**kwargs) -> RewriteService:
    return RewriteService(provider=FakeProvider(**kwargs), model="test-model")


def call(
    method,
    path,
    *,
    body=b"",
    headers=None,
    service=None,
    api_key=None,
    limiter=None,
    client_ip="203.0.113.7",
):
    return process_request(
        method=method,
        path=path,
        body=body,
        headers=headers or {},
        service=service or make_service(),
        default_tone="professional",
        provider_name="fake",
        api_key=api_key,
        limiter=limiter,
        client_ip=client_ip,
    )


def test_healthz():
    status, payload = call("GET", "/healthz")
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["provider"] == "fake"
    assert payload["model"] == "test-model"


def test_root_is_health():
    status, _ = call("GET", "/")
    assert status == 200


def test_tones():
    status, payload = call("GET", "/tones")
    assert status == 200
    keys = {t["key"] for t in payload["tones"]}
    assert "professional" in keys and "translate" in keys


def test_rewrite_success():
    body = json.dumps({"text": "hey can u fix teh report", "tone": "friendly"}).encode()
    status, payload = call("POST", "/rewrite", body=body)
    assert status == 200
    assert payload["text"] == "REWRITTEN"
    assert payload["tone"] == "friendly"
    assert payload["provider"] == "fake"
    assert payload["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_rewrite_defaults_tone_when_absent():
    body = json.dumps({"text": "please tidy up this whole message"}).encode()
    status, payload = call("POST", "/rewrite", body=body)
    assert status == 200
    assert payload["tone"] == "professional"


def test_rewrite_missing_text():
    status, payload = call("POST", "/rewrite", body=b"{}")
    assert status == 400
    assert "text" in payload["error"].lower()


def test_rewrite_invalid_json():
    status, payload = call("POST", "/rewrite", body=b"not json at all")
    assert status == 400
    assert "json" in payload["error"].lower()


def test_rewrite_too_short_is_400():
    body = json.dumps({"text": "hi"}).encode()
    status, _ = call("POST", "/rewrite", body=body)
    assert status == 400


def test_provider_error_is_502():
    body = json.dumps({"text": "this is definitely long enough"}).encode()
    status, payload = call(
        "POST", "/rewrite", body=body, service=make_service(raise_error=True)
    )
    assert status == 502
    assert "error" in payload


def test_auth_required_rejects_missing_key():
    body = json.dumps({"text": "make this a bit nicer please"}).encode()
    status, _ = call("POST", "/rewrite", body=body, api_key="secret")
    assert status == 401


def test_auth_accepts_correct_key():
    body = json.dumps({"text": "make this a bit nicer please"}).encode()
    status, _ = call(
        "POST",
        "/rewrite",
        body=body,
        headers={"authorization": "Bearer secret"},
        api_key="secret",
    )
    assert status == 200


def test_healthz_open_without_key():
    status, _ = call("GET", "/healthz", api_key="secret")
    assert status == 200


def test_healthz_reports_version():
    from proresponse import __version__

    status, payload = call("GET", "/healthz")
    assert status == 200
    assert payload["version"] == __version__


def test_rate_limit_enforced_per_ip():
    from proresponse.ratelimit import RateLimiter

    limiter = RateLimiter(2)  # capacity 2 per key
    service = make_service()
    body = json.dumps({"text": "please make this a bit nicer"}).encode()
    assert call("POST", "/rewrite", body=body, service=service, limiter=limiter)[0] == 200
    assert call("POST", "/rewrite", body=body, service=service, limiter=limiter)[0] == 200
    status, payload = call("POST", "/rewrite", body=body, service=service, limiter=limiter)
    assert status == 429
    assert "rate limit" in payload["error"].lower()
    # A different client IP has its own bucket.
    status, _ = call(
        "POST", "/rewrite", body=body, service=service, limiter=limiter,
        client_ip="198.51.100.9",
    )
    assert status == 200


def test_rate_limit_does_not_touch_get_routes():
    from proresponse.ratelimit import RateLimiter

    limiter = RateLimiter(1)
    body = json.dumps({"text": "please make this a bit nicer"}).encode()
    assert call("POST", "/rewrite", body=body, limiter=limiter)[0] == 200
    # /rewrite bucket is drained, but health/tones are never limited.
    assert call("GET", "/healthz", limiter=limiter)[0] == 200
    assert call("GET", "/tones", limiter=limiter)[0] == 200


def test_auth_checked_before_rate_limit():
    from proresponse.ratelimit import RateLimiter

    limiter = RateLimiter(1)
    body = json.dumps({"text": "please make this a bit nicer"}).encode()
    # An unauthorized caller gets 401 and must not consume a token.
    assert call("POST", "/rewrite", body=body, limiter=limiter, api_key="s")[0] == 401
    status, _ = call(
        "POST", "/rewrite", body=body, limiter=limiter, api_key="s",
        headers={"authorization": "Bearer s"},
    )
    assert status == 200


def test_unexpected_exception_is_500():
    svc = RewriteService(provider=_BoomProvider(), model="m")
    body = json.dumps({"text": "this is long enough to reach the provider"}).encode()
    status, payload = call("POST", "/rewrite", body=body, service=svc)
    assert status == 500
    assert "error" in payload


def test_unknown_route_404():
    status, _ = call("GET", "/nope")
    assert status == 404


def test_wrong_method_405():
    status, _ = call("GET", "/rewrite")
    assert status == 405
