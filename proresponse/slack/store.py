"""Lightweight in-memory state for the Slack app.

Two things need to live between interactions:

* **User preferences** — a user's chosen default tone (and optional model
  override), so ``/pro`` "just works" without repeating the tone every time.
* **Pending rewrites** — the original text behind an ephemeral preview, keyed by
  a short token that fits inside a Slack action ``value``. Regenerate and
  "change tone" reuse it. Entries expire so the store doesn't grow unbounded.

Both are process-local. For a single-instance deployment that's all you need;
to scale horizontally, back these with Redis and keep the same method surface.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

__all__ = ["UserPrefs", "PreferenceStore", "PendingRewrite", "PendingStore"]


@dataclass
class UserPrefs:
    """Per-user settings."""

    tone: str = "professional"
    model: str | None = None


class PreferenceStore:
    """Thread-safe map of user id → :class:`UserPrefs`."""

    def __init__(self, default_tone: str = "professional") -> None:
        self._default_tone = default_tone
        self._prefs: dict[str, UserPrefs] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str) -> UserPrefs:
        with self._lock:
            prefs = self._prefs.get(user_id)
            if prefs is None:
                prefs = UserPrefs(tone=self._default_tone)
                self._prefs[user_id] = prefs
            return UserPrefs(tone=prefs.tone, model=prefs.model)

    def set_tone(self, user_id: str, tone: str) -> None:
        with self._lock:
            prefs = self._prefs.setdefault(
                user_id, UserPrefs(tone=self._default_tone)
            )
            prefs.tone = tone

    def set_model(self, user_id: str, model: str | None) -> None:
        with self._lock:
            prefs = self._prefs.setdefault(
                user_id, UserPrefs(tone=self._default_tone)
            )
            prefs.model = model


@dataclass
class PendingRewrite:
    """The context behind one ephemeral preview.

    ``text`` is the original input; ``result_text`` is the most recently
    generated rewrite currently shown in the preview (what "Post to channel"
    will send). Regenerate and tone changes update ``result_text`` in place.
    """

    text: str
    tone: str
    argument: str | None
    channel: str
    user: str
    result_text: str = ""
    created_at: float = field(default_factory=time.monotonic)


class PendingStore:
    """Token → :class:`PendingRewrite` with time-based expiry.

    Args:
        ttl_seconds: How long a pending entry stays retrievable. Slack's
            ``response_url`` is valid for ~30 minutes, so the default matches.
    """

    def __init__(self, ttl_seconds: float = 1800.0) -> None:
        self._ttl = ttl_seconds
        self._items: dict[str, PendingRewrite] = {}
        self._lock = threading.Lock()

    def put(self, pending: PendingRewrite) -> str:
        token = secrets.token_urlsafe(8)
        with self._lock:
            self._prune_locked()
            self._items[token] = pending
        return token

    def get(self, token: str) -> PendingRewrite | None:
        with self._lock:
            self._prune_locked()
            return self._items.get(token)

    def update(
        self,
        token: str,
        *,
        tone: str | None = None,
        result_text: str | None = None,
    ) -> PendingRewrite | None:
        """Mutate a pending entry's tone and/or latest result text."""

        with self._lock:
            pending = self._items.get(token)
            if pending is not None:
                if tone is not None:
                    pending.tone = tone
                if result_text is not None:
                    pending.result_text = result_text
            return pending

    def discard(self, token: str) -> None:
        with self._lock:
            self._items.pop(token, None)

    def _prune_locked(self) -> None:
        cutoff = time.monotonic() - self._ttl
        stale = [k for k, v in self._items.items() if v.created_at < cutoff]
        for key in stale:
            del self._items[key]
