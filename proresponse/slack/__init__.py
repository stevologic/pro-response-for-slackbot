"""Slack integration for Pro Response (built on ``slack_bolt``)."""

from __future__ import annotations

__all__ = ["build_app", "main"]


def __getattr__(name: str):  # pragma: no cover - thin lazy re-export
    if name in ("build_app", "main"):
        from proresponse.slack.app import build_app, main

        return {"build_app": build_app, "main": main}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
