"""A data-driven catalog of models Pro Response knows about.

This registry is intentionally *just data*. It powers menus, help text, the
docs site, and light validation — but it is never the source of truth for
whether a model exists. Model line-ups move fast; any id may be passed through
config even if it is not listed here (:func:`resolve` returns ``None`` and the
providers still attempt the call). Keeping it declarative means updating for a
new model release is a one-line edit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ModelInfo",
    "MODELS",
    "resolve",
    "models_for_provider",
    "DEFAULTS",
]


@dataclass(frozen=True)
class ModelInfo:
    """Static metadata about a model.

    Attributes:
        id: The model id passed to the provider SDK.
        provider: One of ``"openai"``, ``"anthropic"``, ``"openai-compatible"``.
        label: Friendly display name.
        family: Coarse grouping for menus (e.g. ``"GPT-5"``, ``"Claude"``).
        reasoning: ``True`` for reasoning models, which often reject
            ``temperature`` and prefer larger token budgets.
        notes: Short human-facing description.
    """

    id: str
    provider: str
    label: str
    family: str
    reasoning: bool = False
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


# The line-up is a snapshot for menus/help — providers accept any id regardless.
MODELS: tuple[ModelInfo, ...] = (
    # ---- OpenAI ---------------------------------------------------------
    ModelInfo("gpt-5", "openai", "GPT-5", "GPT-5", reasoning=True,
              notes="Most capable OpenAI model."),
    ModelInfo("gpt-5-mini", "openai", "GPT-5 mini", "GPT-5", reasoning=True,
              notes="Fast, low-cost GPT-5; great default for rewriting."),
    ModelInfo("gpt-5-nano", "openai", "GPT-5 nano", "GPT-5", reasoning=True,
              notes="Cheapest GPT-5 tier."),
    ModelInfo("gpt-4.1", "openai", "GPT-4.1", "GPT-4.1",
              notes="High-quality non-reasoning model."),
    ModelInfo("gpt-4.1-mini", "openai", "GPT-4.1 mini", "GPT-4.1",
              notes="Balanced speed and cost."),
    ModelInfo("gpt-4.1-nano", "openai", "GPT-4.1 nano", "GPT-4.1",
              notes="Fastest GPT-4.1 tier."),
    ModelInfo("gpt-4o", "openai", "GPT-4o", "GPT-4o",
              notes="Omni model; broadly available."),
    ModelInfo("gpt-4o-mini", "openai", "GPT-4o mini", "GPT-4o",
              notes="Small, cheap, widely supported."),
    ModelInfo("o4-mini", "openai", "o4-mini", "o-series", reasoning=True,
              notes="Compact reasoning model."),
    ModelInfo("o3", "openai", "o3", "o-series", reasoning=True,
              notes="Strong reasoning model."),
    # ---- Anthropic ------------------------------------------------------
    ModelInfo("claude-opus-4-8", "anthropic", "Claude Opus 4.8", "Claude",
              notes="Most capable Claude Opus tier."),
    ModelInfo("claude-sonnet-5", "anthropic", "Claude Sonnet 5", "Claude",
              notes="Balanced Claude; fast and capable."),
    ModelInfo("claude-haiku-4-5", "anthropic", "Claude Haiku 4.5", "Claude",
              notes="Fastest, cheapest Claude."),
    ModelInfo("claude-opus-4-7", "anthropic", "Claude Opus 4.7", "Claude",
              notes="Previous-generation Opus."),
    ModelInfo("claude-fable-5", "anthropic", "Claude Fable 5", "Claude",
              reasoning=True,
              notes="Anthropic's most capable widely released model."),
)

_BY_ID: dict[str, ModelInfo] = {}
for _m in MODELS:
    _BY_ID[_m.id] = _m
    for _alias in _m.aliases:
        _BY_ID[_alias] = _m


#: Reasonable per-provider default models. OpenAI is the project default.
DEFAULTS: dict[str, str] = {
    "openai": "gpt-5-mini",
    "anthropic": "claude-sonnet-5",
    "openai-compatible": "gpt-4o-mini",
}


def resolve(model_id: str) -> ModelInfo | None:
    """Return known metadata for ``model_id`` or ``None`` if it isn't listed."""

    return _BY_ID.get(model_id.strip()) if model_id else None


def models_for_provider(provider: str) -> list[ModelInfo]:
    """Return the catalog entries for ``provider`` in display order."""

    return [m for m in MODELS if m.provider == provider]
