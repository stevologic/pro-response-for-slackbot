from __future__ import annotations

from proresponse.ratelimit import RateLimiter


def test_disabled_when_rate_zero():
    limiter = RateLimiter(0)
    assert limiter.enabled is False
    for _ in range(100):
        assert limiter.allow("u1") is True


def test_allows_up_to_capacity_then_blocks():
    limiter = RateLimiter(2)  # capacity 2
    assert limiter.allow("u1") is True
    assert limiter.allow("u1") is True
    assert limiter.allow("u1") is False


def test_keys_are_independent():
    limiter = RateLimiter(1)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True


def test_reset_key():
    limiter = RateLimiter(1)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    limiter.reset("a")
    assert limiter.allow("a") is True


def test_refills_over_time(monkeypatch):
    import proresponse.ratelimit as rl

    clock = {"t": 1000.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock["t"])
    limiter = rl.RateLimiter(60)  # 1 token/sec, capacity 60
    # Drain the burst.
    for _ in range(60):
        assert limiter.allow("u") is True
    assert limiter.allow("u") is False
    # Advance two seconds -> ~2 tokens back.
    clock["t"] += 2.0
    assert limiter.allow("u") is True
    assert limiter.allow("u") is True
