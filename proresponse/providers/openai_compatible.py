"""OpenAI-compatible provider for third-party and local hosts.

Groq, OpenRouter, Together, Azure OpenAI, and local runtimes like Ollama or
vLLM all speak the OpenAI Chat Completions wire format but do **not** implement
the Responses API. This provider reuses the OpenAI client but goes straight to
``chat.completions``, so pointing Pro Response at any of them is just a matter
of setting a base URL and key.
"""

from __future__ import annotations

from proresponse.providers.base import RewriteRequest, RewriteResult
from proresponse.providers.openai_provider import OpenAIProvider
from proresponse.providers.registry import resolve

__all__ = ["OpenAICompatibleProvider"]

_REASONING_MIN_TOKENS = 2048


class OpenAICompatibleProvider(OpenAIProvider):
    """Chat-Completions-only variant of :class:`OpenAIProvider`.

    Args:
        api_key: Key for the host (may be a placeholder for local runtimes).
        base_url: **Required** endpoint, e.g.
            ``https://api.groq.com/openai/v1`` or ``http://localhost:11434/v1``.
        name: Provider label reported in results; defaults to
            ``"openai-compatible"``.
    """

    name = "openai-compatible"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str,
        organization: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            name=name or "openai-compatible",
        )

    def health_check(self) -> bool:
        return bool(self._base_url)

    def rewrite(self, request: RewriteRequest) -> RewriteResult:
        client = self._get_client()
        info = resolve(request.model)
        is_reasoning = bool(info and info.reasoning)
        max_tokens = request.max_output_tokens
        if is_reasoning:
            max_tokens = max(max_tokens, _REASONING_MIN_TOKENS)
        # Compatible hosts almost never expose Responses; skip straight to chat.
        return self._via_chat(
            client, request, max_tokens, allow_temperature=not is_reasoning
        )
