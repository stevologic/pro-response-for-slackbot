"""Provider factory and public exports.

:func:`get_provider` maps a provider name to a constructed
:class:`~proresponse.providers.base.LLMProvider`. Provider modules import their
SDKs lazily, so calling this for ``"openai"`` never imports ``anthropic`` and
vice versa.
"""

from __future__ import annotations

from proresponse.providers.base import (
    LLMProvider,
    ProviderError,
    RewriteRequest,
    RewriteResult,
)

__all__ = [
    "LLMProvider",
    "ProviderError",
    "RewriteRequest",
    "RewriteResult",
    "get_provider",
    "PROVIDERS",
]

#: Provider names Pro Response can construct.
PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "openai-compatible")


def get_provider(
    name: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    organization: str | None = None,
    label: str | None = None,
) -> LLMProvider:
    """Construct a provider by ``name``.

    Args:
        name: One of :data:`PROVIDERS`. ``"openai-compatible"`` accepts the
            aliases ``"compatible"`` and ``"custom"``.
        api_key: API key for the backend.
        base_url: Endpoint override (required for ``openai-compatible``).
        organization: OpenAI organization id (OpenAI only).
        label: Optional display name to report in results.

    Raises:
        ValueError: If ``name`` is not a known provider, or ``base_url`` is
            missing for ``openai-compatible``.
    """

    key = (name or "").strip().lower()

    if key == "openai":
        from proresponse.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            name=label,
        )

    if key == "anthropic":
        from proresponse.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key, base_url=base_url)

    if key in ("openai-compatible", "compatible", "custom"):
        if not base_url:
            raise ValueError(
                "openai-compatible provider requires a base_url "
                "(e.g. https://api.groq.com/openai/v1)."
            )
        from proresponse.providers.openai_compatible import (
            OpenAICompatibleProvider,
        )

        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            name=label,
        )

    raise ValueError(
        f"Unknown provider {name!r}. Choose one of: {', '.join(PROVIDERS)}."
    )
