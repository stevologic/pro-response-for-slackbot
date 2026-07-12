from __future__ import annotations

from proresponse.sanitize import MAX_INPUT_CHARS, sanitize_input


def test_empty_and_none():
    assert sanitize_input("") == ""
    assert sanitize_input(None) == ""


def test_preserves_punctuation_and_case():
    text = "Hello, World! Isn't this great?"
    assert sanitize_input(text) == "Hello, World! Isn't this great?"


def test_unwraps_slack_link_with_label():
    assert sanitize_input("see <https://x.com|our site>") == "see our site"


def test_unwraps_bare_link_and_mentions():
    assert sanitize_input("go to <https://x.com>") == "go to https://x.com"
    assert sanitize_input("hi <@U123|alice>") == "hi alice"
    assert sanitize_input("hi <@U123>") == "hi @U123"
    assert sanitize_input("<!here> ping") == "@here ping"


def test_strips_zero_width_characters():
    dirty = "he​llo"  # zero-width space in the middle
    assert sanitize_input(dirty) == "hello"


def test_collapses_whitespace_but_keeps_newlines():
    assert sanitize_input("a    b\t c") == "a b c"
    assert sanitize_input("line1\n\n\n\nline2") == "line1\n\nline2"


def test_truncates_long_input():
    long = "word " * 4000
    out = sanitize_input(long, max_chars=100)
    assert len(out) <= 101  # room for the ellipsis
    assert out.endswith("…")


def test_default_max_chars_constant():
    assert MAX_INPUT_CHARS >= 1000
