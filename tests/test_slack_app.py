from __future__ import annotations

import pytest

# app.py imports slack_bolt lazily inside build_app, so the parse tests below
# run everywhere; only the wiring test needs slack_bolt installed.
from proresponse.slack.app import _parse_command_text

# --- _parse_command_text -------------------------------------------------


def test_plain_message_uses_default_tone():
    tone, msg = _parse_command_text("can u fix this", "professional")
    assert tone == "professional"
    assert msg == "can u fix this"


def test_leading_tone_word_is_consumed():
    tone, msg = _parse_command_text("friendly can you review this?", "professional")
    assert tone == "friendly"
    assert msg == "can you review this?"


def test_alias_is_consumed_and_canonicalized():
    tone, msg = _parse_command_text("tldr this long message", "professional")
    assert tone == "concise"
    assert msg == "this long message"


def test_non_tone_first_word_stays_in_message():
    tone, msg = _parse_command_text("hello friendly people", "casual")
    assert tone == "casual"
    assert msg == "hello friendly people"


def test_empty_input():
    tone, msg = _parse_command_text("", "professional")
    assert tone == "professional"
    assert msg == ""


def test_tone_only_no_message():
    tone, msg = _parse_command_text("friendly", "professional")
    assert tone == "friendly"
    assert msg == ""


def test_case_insensitive_tone():
    tone, _ = _parse_command_text("FRIENDLY hello there", "professional")
    assert tone == "friendly"


# --- build_app wiring smoke test ----------------------------------------


def test_build_app_wires_without_error():
    """Constructing the Bolt app must register every handler without raising.

    Uses a fake token with token verification disabled, so no network access
    is needed. This catches wiring regressions (bad decorator usage, missing
    imports, renamed action ids) that unit tests on blocks/store can't see.
    """

    pytest.importorskip("slack_bolt")

    from proresponse.config import Settings
    from proresponse.slack.app import build_app

    settings = Settings(
        provider="openai",
        slack_bot_token="xoxb-fake-token-for-wiring-test",
        rate_limit_per_minute=0,
    )
    app = build_app(settings)
    assert app is not None

    # Bolt keeps registered listeners internally; the app should have one per
    # command/action/event/shortcut/view we wire (11 total).
    listeners = getattr(app, "_listeners", None)
    assert listeners is not None and len(listeners) >= 11
