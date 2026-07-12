"""Runtime configuration, loaded from the environment.

A single :class:`Settings` dataclass holds everything the CLI and the Slack app
need. :meth:`Settings.from_env` reads environment variables (loading a ``.env``
file first if ``python-dotenv`` is installed), applies sensible defaults, and
resolves the per-provider default model. This keeps configuration in one place
and free of any framework dependency.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from proresponse.providers import LLMProvider, get_provider
from proresponse.providers.registry import DEFAULTS
from proresponse.transforms import DEFAULT_TRANSFORM

__all__ = ["Settings", "load_dotenv_if_present"]


def load_dotenv_if_present() -> None:
    """Load a ``.env`` file into the environment when possible.

    No-ops if ``python-dotenv`` isn't installed, so it's always safe to call.
    """

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - optional dependency
        return
    load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    """Resolved configuration for a Pro Response process."""

    # --- Model / provider ------------------------------------------------
    provider: str = "openai"
    model: str = ""
    default_transform: str = DEFAULT_TRANSFORM
    temperature: float = 0.3
    max_output_tokens: int = 1024
    max_input_chars: int = 6000

    # --- Credentials -----------------------------------------------------
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    api_base_url: str | None = None
    openai_organization: str | None = None

    # --- Rate limiting ---------------------------------------------------
    rate_limit_per_minute: int = 20

    # --- Slack -----------------------------------------------------------
    slack_bot_token: str | None = None
    slack_app_token: str | None = None
    slack_signing_secret: str | None = None
    slack_mode: str = "socket"  # "socket" or "http"
    host: str = "0.0.0.0"
    port: int = 3000

    # --- Misc ------------------------------------------------------------
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if not self.model:
            self.model = DEFAULTS.get(self.provider, DEFAULTS["openai"])

    @classmethod
    def from_env(cls, *, load_dotenv: bool = True) -> Settings:
        """Build :class:`Settings` from environment variables.

        Recognized variables are documented in ``.env.example``. Legacy names
        from Pro Response 1.x (``OPENAI_API_KEY``, ``SLACK_BOT_TOKEN``, …) are
        still honored so existing deployments keep working.
        """

        if load_dotenv:
            load_dotenv_if_present()

        provider = (os.getenv("PRO_PROVIDER") or "openai").strip().lower()
        return cls(
            provider=provider,
            model=(os.getenv("PRO_MODEL") or "").strip(),
            default_transform=(
                os.getenv("PRO_DEFAULT_TONE") or DEFAULT_TRANSFORM
            ).strip().lower(),
            temperature=_get_float("PRO_TEMPERATURE", 0.3),
            max_output_tokens=_get_int("PRO_MAX_TOKENS", 1024),
            max_input_chars=_get_int("PRO_MAX_INPUT_CHARS", 6000),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            api_base_url=os.getenv("PRO_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            openai_organization=os.getenv("OPENAI_ORG")
            or os.getenv("OPENAI_ORGANIZATION"),
            rate_limit_per_minute=_get_int("PRO_RATE_LIMIT_PER_MINUTE", 20),
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN"),
            slack_app_token=os.getenv("SLACK_APP_TOKEN"),
            slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
            slack_mode=(os.getenv("SLACK_MODE") or "socket").strip().lower(),
            host=os.getenv("SERVICE_IP") or os.getenv("HOST") or "0.0.0.0",
            port=_get_int("SERVICE_PORT", _get_int("PORT", 3000)),
            log_level=(os.getenv("PRO_LOG_LEVEL") or "INFO").strip().upper(),
        )

    # --- Derived helpers -------------------------------------------------
    def api_key_for_provider(self) -> str | None:
        """Return the credential matching the configured provider."""

        if self.provider == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key

    def build_provider(self) -> LLMProvider:
        """Construct the configured :class:`LLMProvider`."""

        return get_provider(
            self.provider,
            api_key=self.api_key_for_provider(),
            base_url=self.api_base_url,
            organization=self.openai_organization,
        )
