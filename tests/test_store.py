from __future__ import annotations

from proresponse.slack.store import (
    PendingRewrite,
    PendingStore,
    PreferenceStore,
)


def make_pending(**overrides) -> PendingRewrite:
    defaults = dict(
        text="original text",
        tone="professional",
        argument=None,
        channel="C123",
        user="U123",
        result_text="rewritten",
    )
    defaults.update(overrides)
    return PendingRewrite(**defaults)


# --- PreferenceStore -----------------------------------------------------


def test_prefs_default_tone():
    prefs = PreferenceStore(default_tone="friendly")
    assert prefs.get("U1").tone == "friendly"


def test_prefs_set_tone_and_model():
    prefs = PreferenceStore(default_tone="professional")
    prefs.set_tone("U1", "concise")
    prefs.set_model("U1", "gpt-4.1")
    got = prefs.get("U1")
    assert got.tone == "concise"
    assert got.model == "gpt-4.1"


def test_prefs_get_returns_copy():
    prefs = PreferenceStore()
    snapshot = prefs.get("U1")
    snapshot.tone = "casual"  # mutating the copy must not affect the store
    assert prefs.get("U1").tone == "professional"


def test_prefs_users_independent():
    prefs = PreferenceStore()
    prefs.set_tone("U1", "formal")
    assert prefs.get("U2").tone == "professional"


# --- PendingStore --------------------------------------------------------


def test_pending_put_get_roundtrip():
    store = PendingStore()
    token = store.put(make_pending())
    item = store.get(token)
    assert item is not None
    assert item.text == "original text"
    assert item.result_text == "rewritten"


def test_pending_tokens_unique():
    store = PendingStore()
    tokens = {store.put(make_pending()) for _ in range(50)}
    assert len(tokens) == 50


def test_pending_update_tone_and_result():
    store = PendingStore()
    token = store.put(make_pending())
    store.update(token, tone="soften", result_text="softer version")
    item = store.get(token)
    assert item.tone == "soften"
    assert item.result_text == "softer version"


def test_pending_update_unknown_token_returns_none():
    store = PendingStore()
    assert store.update("nope", tone="x") is None


def test_pending_discard():
    store = PendingStore()
    token = store.put(make_pending())
    store.discard(token)
    assert store.get(token) is None
    store.discard(token)  # idempotent


def test_pending_expiry(monkeypatch):
    import proresponse.slack.store as st

    clock = {"t": 1000.0}
    monkeypatch.setattr(st.time, "monotonic", lambda: clock["t"])
    store = PendingStore(ttl_seconds=60.0)
    # Pass created_at explicitly: the dataclass default_factory captured the
    # real time.monotonic before the monkeypatch, so it would use the real clock.
    token = store.put(make_pending(created_at=clock["t"]))
    clock["t"] += 30
    assert store.get(token) is not None
    clock["t"] += 61
    assert store.get(token) is None
