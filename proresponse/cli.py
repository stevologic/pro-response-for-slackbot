"""Command-line interface for Pro Response.

Handy for trying tones without Slack, scripting rewrites in a pipeline, and
launching the Slack bot. Configuration comes from the environment (see
``.env.example``); every relevant value can be overridden with a flag.

Examples::

    proresponse rewrite "hey can u send me teh report" --tone professional
    echo "make this nicer" | proresponse rewrite --tone friendly
    proresponse tones
    proresponse models --provider anthropic
    proresponse slack
"""

from __future__ import annotations

import argparse
import json
import sys

from proresponse import __version__
from proresponse.config import Settings
from proresponse.core import RewriteService
from proresponse.providers import ProviderError, get_provider
from proresponse.providers.registry import MODELS, models_for_provider
from proresponse.transforms import list_transforms

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proresponse",
        description="Pro Response — an AI writing assistant for teams.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    # rewrite -----------------------------------------------------------
    rw = sub.add_parser("rewrite", help="Rewrite text with a chosen tone.")
    rw.add_argument("text", nargs="?", help="Text to rewrite (or pipe via stdin).")
    rw.add_argument("-t", "--tone", default=None, help="Transform/tone key.")
    rw.add_argument(
        "-a",
        "--arg",
        default=None,
        help="Argument for tones that need one (translate, custom).",
    )
    rw.add_argument("--provider", default=None, help="Override provider.")
    rw.add_argument("--model", default=None, help="Override model id.")
    rw.add_argument("--base-url", default=None, help="Override API base URL.")
    rw.add_argument("--temperature", type=float, default=None)
    rw.add_argument("--max-tokens", type=int, default=None)
    rw.add_argument(
        "--json", action="store_true", help="Emit a JSON object with metadata."
    )

    # tones -------------------------------------------------------------
    sub.add_parser("tones", help="List available tones/transforms.")

    # models ------------------------------------------------------------
    md = sub.add_parser("models", help="List known models.")
    md.add_argument("--provider", default=None, help="Filter by provider.")

    # slack -------------------------------------------------------------
    sub.add_parser("slack", help="Run the Slack bot.")

    return parser


def _cmd_tones() -> int:
    print("Available tones:\n")
    for tf in list_transforms():
        arg = " (takes an argument)" if tf.takes_argument else ""
        print(f"  {tf.key:<12} {tf.description}{arg}")
    return 0


def _cmd_models(provider: str | None) -> int:
    catalog = models_for_provider(provider) if provider else list(MODELS)
    if not catalog:
        print(f"No known models for provider {provider!r}.", file=sys.stderr)
        return 1
    print(f"{'MODEL':<22}{'PROVIDER':<20}{'NOTES'}")
    for m in catalog:
        print(f"{m.id:<22}{m.provider:<20}{m.notes}")
    return 0


def _cmd_rewrite(args: argparse.Namespace, settings: Settings) -> int:
    text = args.text
    if text is None:
        # Read from stdin when no positional text is given.
        text = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not text or not text.strip():
        print("No input text provided.", file=sys.stderr)
        return 2

    provider_name = args.provider or settings.provider
    api_key = (
        settings.anthropic_api_key
        if provider_name == "anthropic"
        else settings.openai_api_key
    )
    try:
        provider = get_provider(
            provider_name,
            api_key=api_key,
            base_url=args.base_url or settings.api_base_url,
            organization=settings.openai_organization,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    service = RewriteService(
        provider=provider,
        model=args.model or settings.model,
        temperature=args.temperature
        if args.temperature is not None
        else settings.temperature,
        max_output_tokens=args.max_tokens or settings.max_output_tokens,
        max_input_chars=settings.max_input_chars,
    )

    try:
        result = service.rewrite(
            text,
            transform=args.tone or settings.default_transform,
            argument=args.arg,
        )
    except ValueError as exc:  # too-short input
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except ProviderError as exc:
        print(f"Provider error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "text": result.text,
                    "model": result.model,
                    "provider": result.provider,
                    "usage": result.usage,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(result.text)
    return 0


def _cmd_slack() -> int:
    # Imported lazily so the CLI works without slack_bolt installed.
    from proresponse.slack.app import main as slack_main

    return slack_main()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "rewrite"):
        settings = Settings.from_env()
        # ``proresponse`` with no subcommand behaves like ``rewrite`` reading
        # stdin, but only if there's piped input; otherwise show help.
        if args.command is None:
            if sys.stdin.isatty():
                parser.print_help()
                return 0
            args = parser.parse_args(["rewrite"])
        return _cmd_rewrite(args, settings)

    if args.command == "tones":
        return _cmd_tones()
    if args.command == "models":
        return _cmd_models(args.provider)
    if args.command == "slack":
        return _cmd_slack()

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
