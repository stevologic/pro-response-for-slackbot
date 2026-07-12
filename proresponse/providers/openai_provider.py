"""OpenAI provider — the project default backend.

Uses the modern **Responses API** (``client.responses.create``) with a
Chat Completions fallback for endpoints that don't expose Responses yet. The
provider is defensive about model-specific parameter rules: reasoning models
(GPT-5, o-series) frequently reject ``temperature`` and need a larger token
budget, so the call automatically retries without the offending parameter
rather than failing the whole request.
"""

from __future__ import annotations

import logging

from proresponse.providers.base import (
    LLMProvider,
    ProviderError,
    RewriteRequest,
    RewriteResult,
)
from proresponse.providers.registry import resolve

log = logging.getLogger(__name__)

__all__ = ["OpenAIProvider"]

# Reasoning models spend part of their token budget on hidden reasoning, so a
# short cap can yield an empty visible answer. Give them headroom.
_REASONING_MIN_TOKENS = 2048


class OpenAIProvider(LLMProvider):
    """Talk to OpenAI (or any OpenAI SDK-compatible host).

    Args:
        api_key: OpenAI API key. When ``None`` the SDK falls back to the
            ``OPENAI_API_KEY`` environment variable.
        base_url: Optional override for OpenAI-compatible hosts.
        organization: Optional OpenAI organization id.
        name: Provider name to report in results (subclasses override).
    """

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        organization: str | None = None,
        name: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._organization = organization
        if name:
            self.name = name
        self._client = None  # constructed lazily so imports stay cheap

    # -- client management ----------------------------------------------
    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderError(
                "The 'openai' package is not installed. Install it with "
                "`pip install openai`.",
                cause=exc,
            ) from exc

        kwargs: dict[str, object] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._organization:
            kwargs["organization"] = self._organization
        self._client = OpenAI(**kwargs)
        return self._client

    def health_check(self) -> bool:
        import os

        return bool(self._api_key or os.getenv("OPENAI_API_KEY") or self._base_url)

    # -- main entry point ------------------------------------------------
    def rewrite(self, request: RewriteRequest) -> RewriteResult:
        client = self._get_client()
        info = resolve(request.model)
        is_reasoning = bool(info and info.reasoning)
        max_tokens = request.max_output_tokens
        if is_reasoning:
            max_tokens = max(max_tokens, _REASONING_MIN_TOKENS)

        # Prefer the Responses API; fall back to Chat Completions if the host or
        # SDK version doesn't support it.
        try:
            return self._via_responses(
                client, request, max_tokens, allow_temperature=not is_reasoning
            )
        except _ResponsesUnavailable:
            log.debug("Responses API unavailable; using chat.completions")
            return self._via_chat(
                client, request, max_tokens, allow_temperature=not is_reasoning
            )

    # -- Responses API ---------------------------------------------------
    def _via_responses(
        self,
        client,
        request: RewriteRequest,
        max_tokens: int,
        *,
        allow_temperature: bool,
    ) -> RewriteResult:
        if not hasattr(client, "responses"):
            raise _ResponsesUnavailable

        kwargs: dict[str, object] = {
            "model": request.model,
            "instructions": request.system_prompt,
            "input": request.text,
            "max_output_tokens": max_tokens,
        }
        if allow_temperature:
            kwargs["temperature"] = request.temperature

        try:
            resp = client.responses.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalized below
            if _is_unsupported_param(exc) and "temperature" in kwargs:
                # Model rejects temperature: retry once without it.
                kwargs.pop("temperature")
                resp = client.responses.create(**kwargs)
            elif _looks_like_missing_endpoint(exc):
                raise _ResponsesUnavailable from exc
            else:
                raise self._to_provider_error(exc) from exc

        text = getattr(resp, "output_text", None)
        if not text:
            text = _extract_responses_text(resp)
        if not text:
            raise ProviderError("The model returned an empty response.")
        return RewriteResult(
            text=text.strip(),
            model=getattr(resp, "model", request.model),
            provider=self.name,
            usage=_usage_from_responses(resp),
        )

    # -- Chat Completions fallback --------------------------------------
    def _via_chat(
        self,
        client,
        request: RewriteRequest,
        max_tokens: int,
        *,
        allow_temperature: bool,
    ) -> RewriteResult:
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.text},
        ]
        kwargs: dict[str, object] = {
            "model": request.model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if allow_temperature:
            kwargs["temperature"] = request.temperature

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalized below
            if _is_unsupported_param(exc):
                # Retry dropping the two most common culprits.
                kwargs.pop("temperature", None)
                if "max_completion_tokens" in str(exc):
                    kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
                resp = client.chat.completions.create(**kwargs)
            else:
                raise self._to_provider_error(exc) from exc

        text = resp.choices[0].message.content if resp.choices else None
        if not text:
            raise ProviderError("The model returned an empty response.")
        return RewriteResult(
            text=text.strip(),
            model=getattr(resp, "model", request.model),
            provider=self.name,
            usage=_usage_from_chat(resp),
        )

    # -- error normalization --------------------------------------------
    def _to_provider_error(self, exc: Exception) -> ProviderError:
        name = type(exc).__name__
        message = str(exc)
        if "Authentication" in name or "PermissionDenied" in name:
            return ProviderError(
                "Authentication with OpenAI failed. Check the API key.",
                cause=exc,
            )
        if "RateLimit" in name:
            return ProviderError(
                "OpenAI rate limit reached. Please try again shortly.",
                cause=exc,
            )
        if "NotFound" in name:
            return ProviderError(
                f"Model not found or unavailable: {message}", cause=exc
            )
        if "Connection" in name or "Timeout" in name:
            return ProviderError(
                "Could not reach OpenAI. Please try again.", cause=exc
            )
        return ProviderError(f"OpenAI request failed: {message}", cause=exc)


class _ResponsesUnavailable(Exception):
    """Internal signal that the Responses API can't be used on this host."""


def _is_unsupported_param(exc: Exception) -> bool:
    text = str(exc).lower()
    return "unsupported" in text and ("param" in text or "temperature" in text) or (
        "temperature" in text and "does not support" in text
    ) or "unsupported_parameter" in text


def _looks_like_missing_endpoint(exc: Exception) -> bool:
    text = str(exc).lower()
    return "responses" in text and ("not found" in text or "no such" in text)


def _extract_responses_text(resp) -> str:
    """Walk a Responses object for text when ``output_text`` is absent."""

    parts: list[str] = []
    for item in getattr(resp, "output", []) or []:
        for block in getattr(item, "content", []) or []:
            value = getattr(block, "text", None)
            if isinstance(value, str):
                parts.append(value)
    return "".join(parts)


def _usage_from_responses(resp) -> dict[str, int] | None:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }


def _usage_from_chat(resp) -> dict[str, int] | None:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
    }
