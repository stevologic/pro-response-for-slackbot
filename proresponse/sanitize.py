"""Input cleaning for messages before they reach a model.

The original Pro Response stripped every non-alphanumeric character, which
destroyed punctuation, code, URLs, and ``@mentions`` — exactly the things a
writing assistant must keep. This module takes the opposite approach: it
normalizes whitespace and length but preserves the content, and it neutralizes
Slack's control sequences so they can't be mistaken for prompt instructions.
"""

from __future__ import annotations

import re

__all__ = ["sanitize_input", "MAX_INPUT_CHARS"]

# Slack wraps links, users, and channels in angle-bracket tokens like
# ``<https://x|label>`` or ``<@U123|name>``. We keep the human-facing label and
# drop the machine id so the model sees readable text.
_SLACK_LINK = re.compile(r"<(?P<target>[^|>]+)(?:\|(?P<label>[^>]*))?>")

# Collapse runs of horizontal whitespace but keep newlines meaningful.
_HSPACE = re.compile(r"[ \t\f\v]+")
# Collapse 3+ blank lines down to a single blank line.
_BLANK_LINES = re.compile(r"\n{3,}")

# Zero-width and bidirectional control characters are a common prompt-injection
# and homoglyph vector; strip them outright.
_INVISIBLES = re.compile(
    "[​‌‍‎‏‪-‮⁠﻿]"
)

# A generous ceiling. Slack slash-command payloads are already bounded, but this
# guards the model call (and our bill) against pathological input.
MAX_INPUT_CHARS = 6000


def _replace_slack_token(match: re.Match[str]) -> str:
    target = match.group("target")
    label = match.group("label")
    if label:
        return label
    # Strip the leading sigil from bare user/channel/special mentions so
    # ``<@U123>`` becomes ``@U123`` rather than a dangling token.
    if target.startswith("@"):
        return target
    if target.startswith("#"):
        return target
    if target.startswith("!"):
        # <!here>, <!channel>, <!everyone>
        return "@" + target[1:]
    return target


def sanitize_input(text: str | None, *, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Return a cleaned version of ``text`` suitable for a model prompt.

    The transformation is intentionally conservative — it keeps punctuation and
    structure so the writing assistant has something real to work with:

    * unwrap Slack link/mention tokens to their readable form,
    * remove zero-width / bidi control characters,
    * normalize horizontal whitespace and excessive blank lines,
    * trim to ``max_chars`` on a word boundary where possible.
    """

    if not text:
        return ""

    cleaned = _SLACK_LINK.sub(_replace_slack_token, text)
    cleaned = _INVISIBLES.sub("", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _HSPACE.sub(" ", cleaned)
    cleaned = _BLANK_LINES.sub("\n\n", cleaned)
    # Trim trailing spaces on each line, then surrounding whitespace overall.
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n")).strip()

    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
        # Prefer cutting at the last whitespace so we don't split a word.
        cut = cleaned.rsplit(None, 1)[0] if " " in cleaned else cleaned
        cleaned = cut.rstrip() + "…"  # ellipsis marks the truncation

    return cleaned
