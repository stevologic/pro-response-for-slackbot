"""Pro Response — an AI writing assistant for Slack.

Pro Response rewrites, refines, and reformats team messages using modern LLMs
(OpenAI, Anthropic, and any OpenAI-compatible endpoint). It ships with a
``slack_bolt`` app, a provider-agnostic model layer, and a local CLI.

The package is intentionally import-light: importing :mod:`proresponse` pulls in
only pure-Python helpers. Heavy optional dependencies (``openai``,
``anthropic``, ``slack_bolt``) are imported lazily inside the modules that need
them, so ``from proresponse import transforms`` works without any provider SDK
installed.
"""

from __future__ import annotations

__all__ = [
    "__version__",
    "get_provider",
    "rewrite",
]

__version__ = "2.0.0"


def __getattr__(name: str):  # pragma: no cover - thin lazy re-export
    # Lazy attribute access keeps ``import proresponse`` cheap while still
    # exposing the two most common entry points at the top level.
    if name == "get_provider":
        from proresponse.providers import get_provider

        return get_provider
    if name == "rewrite":
        from proresponse.core import rewrite

        return rewrite
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
