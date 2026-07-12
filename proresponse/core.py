"""The rewrite pipeline: sanitize → build prompt → call provider.

This is the seam every front-end (CLI, Slack) shares. :class:`RewriteService`
binds a provider and defaults together so callers just pass text and a tone;
:func:`rewrite` is a stateless convenience for one-off use.
"""

from __future__ import annotations

from dataclasses import dataclass

from proresponse.providers.base import (
    LLMProvider,
    ProviderError,
    RewriteRequest,
    RewriteResult,
)
from proresponse.sanitize import sanitize_input
from proresponse.transforms import build_system_prompt, get_transform

__all__ = ["RewriteService", "rewrite", "ProviderError", "MIN_INPUT_CHARS"]

# Below this length there's nothing meaningful to rewrite; the original bot used
# the same threshold to avoid spending a call on a stray keystroke.
MIN_INPUT_CHARS = 3


@dataclass
class RewriteService:
    """Bind a provider and defaults for repeated rewrites.

    Attributes:
        provider: The backend to call.
        model: Default model id.
        temperature: Default sampling temperature.
        max_output_tokens: Default generation cap.
        max_input_chars: Truncate incoming text to this many characters.
    """

    provider: LLMProvider
    model: str
    temperature: float = 0.3
    max_output_tokens: int = 1024
    max_input_chars: int = 6000

    def rewrite(
        self,
        text: str,
        *,
        transform: str = "professional",
        argument: str | None = None,
        model: str | None = None,
    ) -> RewriteResult:
        """Rewrite ``text`` using ``transform``.

        Args:
            text: Raw user input (sanitized internally).
            transform: A transform key or alias (see
                :mod:`proresponse.transforms`).
            argument: Free-text argument for transforms that need one
                (``translate``, ``custom``).
            model: Optional per-call model override.

        Raises:
            ValueError: If the sanitized text is too short to rewrite.
            ProviderError: If the backend call fails.
        """

        clean = sanitize_input(text, max_chars=self.max_input_chars)
        if len(clean) < MIN_INPUT_CHARS:
            raise ValueError(
                "That message is too short to rewrite — give me a bit more text."
            )

        tf = get_transform(transform)
        system_prompt = build_system_prompt(tf, argument)
        request = RewriteRequest(
            system_prompt=system_prompt,
            text=clean,
            model=model or self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        return self.provider.rewrite(request)


def rewrite(
    text: str,
    *,
    provider: LLMProvider,
    model: str,
    transform: str = "professional",
    argument: str | None = None,
    temperature: float = 0.3,
    max_output_tokens: int = 1024,
    max_input_chars: int = 6000,
) -> RewriteResult:
    """One-shot rewrite without constructing a :class:`RewriteService`."""

    service = RewriteService(
        provider=provider,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        max_input_chars=max_input_chars,
    )
    return service.rewrite(text, transform=transform, argument=argument)
