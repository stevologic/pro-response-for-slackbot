"""Provider-agnostic contract for turning a message into a rewrite.

Every backend (OpenAI, Anthropic, OpenAI-compatible) implements
:class:`LLMProvider`. The Slack app and CLI only ever see this interface plus
the two small dataclasses below, so swapping or adding a provider never touches
call sites.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

__all__ = [
    "RewriteRequest",
    "RewriteResult",
    "LLMProvider",
    "ProviderError",
]


class ProviderError(RuntimeError):
    """Raised when a provider cannot complete a request.

    Carries a human-readable message safe to surface to a Slack user, plus the
    originating exception for logs.
    """

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


@dataclass
class RewriteRequest:
    """Everything a provider needs to produce one rewrite.

    Attributes:
        system_prompt: The composed instruction (see
            :func:`proresponse.transforms.build_system_prompt`).
        text: The already-sanitized user message.
        model: The model id to call.
        temperature: Sampling temperature. Providers/models that reject the
            parameter drop it automatically.
        max_output_tokens: Upper bound on generated tokens.
    """

    system_prompt: str
    text: str
    model: str
    temperature: float = 0.3
    max_output_tokens: int = 1024


@dataclass
class RewriteResult:
    """The outcome of a rewrite.

    Attributes:
        text: The rewritten message.
        model: The model that actually served the request.
        provider: The provider name (``"openai"``, ``"anthropic"``, …).
        usage: Best-effort token accounting; empty when the SDK doesn't report
            it. Keys: ``input_tokens``, ``output_tokens``.
    """

    text: str
    model: str
    provider: str
    usage: dict[str, int] | None = None


class LLMProvider(abc.ABC):
    """Base class for a rewrite backend."""

    #: Short, stable provider name used in config and results.
    name: str = "base"

    @abc.abstractmethod
    def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Produce a rewrite for ``request`` or raise :class:`ProviderError`."""

    def health_check(self) -> bool:  # pragma: no cover - overridden as needed
        """Return ``True`` if the provider looks usable (credentials present).

        The default only checks that a client can be constructed; it does not
        make a network call.
        """

        return True
