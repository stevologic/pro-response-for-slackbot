"""Anthropic (Claude) provider.

Uses the official ``anthropic`` SDK and the Messages API. For a lightweight
rewrite task we keep the request minimal and portable across the whole current
Claude line-up: ``system`` + a single user message + ``max_tokens``. We
deliberately do **not** send ``temperature`` or ``thinking`` — current Claude
models (Opus 4.7+/4.8, Sonnet 5, Fable 5) reject non-default sampling
parameters, and omitting them is accepted by every model, so this one code path
works whether the configured model is a Haiku or a Fable.
"""

from __future__ import annotations

import logging

from proresponse.providers.base import (
    LLMProvider,
    ProviderError,
    RewriteRequest,
    RewriteResult,
)

log = logging.getLogger(__name__)

__all__ = ["AnthropicProvider"]


class AnthropicProvider(LLMProvider):
    """Talk to the Anthropic Messages API.

    Args:
        api_key: Anthropic API key. When ``None`` the SDK falls back to
            ``ANTHROPIC_API_KEY``.
        base_url: Optional endpoint override.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderError(
                "The 'anthropic' package is not installed. Install it with "
                "`pip install anthropic`.",
                cause=exc,
            ) from exc
        kwargs: dict[str, object] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._client = Anthropic(**kwargs)
        return self._client

    def health_check(self) -> bool:
        import os

        return bool(self._api_key or os.getenv("ANTHROPIC_API_KEY"))

    def rewrite(self, request: RewriteRequest) -> RewriteResult:
        client = self._get_client()
        try:
            resp = client.messages.create(
                model=request.model,
                max_tokens=request.max_output_tokens,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.text}],
            )
        except Exception as exc:  # noqa: BLE001 - normalized below
            raise self._to_provider_error(exc) from exc

        if getattr(resp, "stop_reason", None) == "refusal":
            raise ProviderError(
                "The model declined to rewrite this message."
            )

        text = _first_text_block(resp)
        if not text:
            raise ProviderError("The model returned an empty response.")
        return RewriteResult(
            text=text.strip(),
            model=getattr(resp, "model", request.model),
            provider=self.name,
            usage=_usage(resp),
        )

    def _to_provider_error(self, exc: Exception) -> ProviderError:
        name = type(exc).__name__
        message = str(exc)
        if "Authentication" in name or "PermissionDenied" in name:
            return ProviderError(
                "Authentication with Anthropic failed. Check the API key.",
                cause=exc,
            )
        if "RateLimit" in name:
            return ProviderError(
                "Anthropic rate limit reached. Please try again shortly.",
                cause=exc,
            )
        if "NotFound" in name:
            return ProviderError(
                f"Model not found or unavailable: {message}", cause=exc
            )
        if "Connection" in name or "Timeout" in name:
            return ProviderError(
                "Could not reach Anthropic. Please try again.", cause=exc
            )
        return ProviderError(f"Anthropic request failed: {message}", cause=exc)


def _first_text_block(resp) -> str:
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            value = getattr(block, "text", None)
            if isinstance(value, str) and value:
                return value
    return ""


def _usage(resp) -> dict[str, int] | None:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }
