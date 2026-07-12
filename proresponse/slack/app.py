"""The Slack Bolt app: slash commands, shortcuts, actions, and App Home.

``build_app`` wires everything against a :class:`~proresponse.config.Settings`
and returns a ready ``slack_bolt.App``. ``main`` starts it in Socket Mode (the
default — no public URL needed) or HTTP mode.

Interaction surfaces
--------------------
* ``/pro`` / ``/pr`` — rewrite and show an interactive ephemeral preview with
  Post / Regenerate / Change-tone / Discard controls.
* ``/prr`` — a private recommendation only (legacy Pro Response 1.x behavior).
* Message shortcut *Pro Response: rewrite* — refine an existing message.
* Global shortcut *Compose with Pro Response* — a modal to draft from scratch.
* App Home — help and a default-tone picker.
"""

from __future__ import annotations

import logging

from proresponse.config import Settings
from proresponse.core import RewriteService
from proresponse.providers import ProviderError
from proresponse.ratelimit import RateLimiter
from proresponse.slack import blocks
from proresponse.slack.store import PendingRewrite, PendingStore, PreferenceStore
from proresponse.transforms import get_transform, is_transform

log = logging.getLogger(__name__)

__all__ = ["build_app", "main"]

_TOO_FAST = "You're going a bit fast — give me a moment and try again. :hourglass:"
_EXPIRED = "This preview has expired. Run the command again to start over."


def _parse_command_text(raw: str, default_tone: str) -> tuple[str, str]:
    """Split ``/pro`` text into ``(tone_key, message)``.

    If the first word names a tone (``/pro friendly hi there``) it is consumed
    as the tone selector; otherwise the whole string is the message and the
    user's default tone applies.
    """

    raw = (raw or "").strip()
    if not raw:
        return default_tone, ""
    parts = raw.split(None, 1)
    first = parts[0].lower()
    if is_transform(first):
        message = parts[1] if len(parts) > 1 else ""
        return get_transform(first).key, message
    return default_tone, raw


def _error_view(message: str) -> dict:
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Pro Response"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": blocks.error_blocks(message),
    }


def build_app(settings: Settings) -> object:
    """Construct and wire the Bolt ``App`` for ``settings``.

    Raises:
        RuntimeError: If ``slack_bolt`` isn't installed.
    """

    try:
        from slack_bolt import App
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(
            "slack_bolt is not installed. Install the Slack extra with "
            "`pip install 'proresponse[slack]'`."
        ) from exc

    provider = settings.build_provider()
    service = RewriteService(
        provider=provider,
        model=settings.model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        max_input_chars=settings.max_input_chars,
    )
    prefs = PreferenceStore(default_tone=settings.default_transform)
    pending = PendingStore()
    limiter = RateLimiter(settings.rate_limit_per_minute)

    app_kwargs: dict[str, object] = {"token": settings.slack_bot_token}
    if settings.slack_signing_secret:
        app_kwargs["signing_secret"] = settings.slack_signing_secret
    # Socket Mode verifies via the app-level token, so a signing secret isn't
    # required there; allow the app to construct without one.
    app_kwargs["token_verification_enabled"] = False
    app = App(**app_kwargs)

    # -- helpers --------------------------------------------------------
    def _run_rewrite(text: str, tone: str, user: str, argument: str | None = None):
        model = prefs.get(user).model
        return service.rewrite(text, transform=tone, argument=argument, model=model)

    # -- slash commands -------------------------------------------------
    def _handle_preview_command(ack, command, respond):
        ack()
        user = command["user_id"]
        channel = command["channel_id"]
        if not limiter.allow(user):
            respond(response_type="ephemeral", text=_TOO_FAST)
            return
        default = prefs.get(user).tone
        tone, message = _parse_command_text(command.get("text", ""), default)
        if not message.strip():
            respond(
                response_type="ephemeral",
                blocks=blocks.error_blocks(
                    "Give me something to rewrite, e.g. "
                    "`/pro can u send me teh report`."
                ),
            )
            return
        try:
            result = _run_rewrite(message, tone, user)
        except (ValueError, ProviderError) as exc:
            respond(response_type="ephemeral", blocks=blocks.error_blocks(str(exc)))
            return
        token = pending.put(
            PendingRewrite(
                text=message,
                tone=tone,
                argument=None,
                channel=channel,
                user=user,
                result_text=result.text,
            )
        )
        respond(
            response_type="ephemeral",
            blocks=blocks.preview_blocks(token, result, tone),
        )

    @app.command("/pro")
    def cmd_pro(ack, command, respond):
        _handle_preview_command(ack, command, respond)

    @app.command("/pr")
    def cmd_pr(ack, command, respond):
        _handle_preview_command(ack, command, respond)

    @app.command("/prr")
    def cmd_prr(ack, command, respond):
        ack()
        user = command["user_id"]
        if not limiter.allow(user):
            respond(response_type="ephemeral", text=_TOO_FAST)
            return
        default = prefs.get(user).tone
        tone, message = _parse_command_text(command.get("text", ""), default)
        if not message.strip():
            respond(
                response_type="ephemeral",
                blocks=blocks.error_blocks(
                    "Give me something to rewrite, e.g. `/prr fix this pls`."
                ),
            )
            return
        try:
            result = _run_rewrite(message, tone, user)
        except (ValueError, ProviderError) as exc:
            respond(response_type="ephemeral", blocks=blocks.error_blocks(str(exc)))
            return
        respond(
            response_type="ephemeral",
            blocks=blocks.recommendation_blocks(message, result),
        )

    # -- interactive actions -------------------------------------------
    @app.action(blocks.ACTION_POST)
    def act_post(ack, body, respond, client):
        ack()
        token = body["actions"][0].get("value", "")
        item = pending.get(token)
        if item is None or not item.result_text:
            respond(replace_original=True, text=_EXPIRED)
            return
        try:
            client.chat_postMessage(channel=item.channel, text=item.result_text)
        except Exception as exc:  # noqa: BLE001 - Slack API error surface
            log.warning("post_to_channel failed: %s", exc)
            respond(
                replace_original=False,
                response_type="ephemeral",
                text=(
                    "I couldn't post there — make sure I've been added to the "
                    "channel, then try again."
                ),
            )
            return
        pending.discard(token)
        respond(replace_original=True, text=":white_check_mark: Posted to the channel.")

    @app.action(blocks.ACTION_REGEN)
    def act_regen(ack, body, respond):
        ack()
        token = body["actions"][0].get("value", "")
        item = pending.get(token)
        if item is None:
            respond(replace_original=True, text=_EXPIRED)
            return
        if not limiter.allow(item.user):
            respond(response_type="ephemeral", replace_original=False, text=_TOO_FAST)
            return
        try:
            result = _run_rewrite(item.text, item.tone, item.user, item.argument)
        except (ValueError, ProviderError) as exc:
            respond(response_type="ephemeral", replace_original=False,
                    blocks=blocks.error_blocks(str(exc)))
            return
        pending.update(token, result_text=result.text)
        respond(replace_original=True, blocks=blocks.preview_blocks(token, result, item.tone))

    @app.action(blocks.ACTION_TONE)
    def act_change_tone(ack, body, respond):
        ack()
        action = body["actions"][0]
        token = blocks.token_from_block_id(action.get("block_id"))
        selected = action.get("selected_option", {}).get("value", "professional")
        item = pending.get(token) if token else None
        if item is None:
            respond(replace_original=True, text=_EXPIRED)
            return
        if not limiter.allow(item.user):
            respond(response_type="ephemeral", replace_original=False, text=_TOO_FAST)
            return
        pending.update(token, tone=selected)
        try:
            result = _run_rewrite(item.text, selected, item.user, item.argument)
        except (ValueError, ProviderError) as exc:
            respond(response_type="ephemeral", replace_original=False,
                    blocks=blocks.error_blocks(str(exc)))
            return
        pending.update(token, result_text=result.text)
        respond(replace_original=True, blocks=blocks.preview_blocks(token, result, selected))

    @app.action(blocks.ACTION_DISCARD)
    def act_discard(ack, body, respond):
        ack()
        token = body["actions"][0].get("value", "")
        pending.discard(token)
        respond(replace_original=True, text=":wastebasket: Discarded.")

    @app.action(blocks.ACTION_HOME_TONE)
    def act_home_tone(ack, body, client):
        ack()
        user = body["user"]["id"]
        selected = body["actions"][0].get("selected_option", {}).get("value")
        if selected:
            prefs.set_tone(user, selected)
        client.views_publish(
            user_id=user, view=blocks.home_view(prefs.get(user).tone)
        )

    # -- App Home -------------------------------------------------------
    @app.event("app_home_opened")
    def home_opened(event, client):
        user = event["user"]
        client.views_publish(
            user_id=user, view=blocks.home_view(prefs.get(user).tone)
        )

    # -- shortcuts ------------------------------------------------------
    @app.shortcut("proresponse_rewrite")
    def shortcut_message(ack, shortcut, client):
        ack()
        user = shortcut["user"]["id"]
        channel = shortcut["channel"]["id"]
        text = shortcut.get("message", {}).get("text", "")
        if not limiter.allow(user):
            client.chat_postEphemeral(channel=channel, user=user, text=_TOO_FAST)
            return
        tone = prefs.get(user).tone
        try:
            result = _run_rewrite(text, tone, user)
        except (ValueError, ProviderError) as exc:
            client.chat_postEphemeral(
                channel=channel, user=user, blocks=blocks.error_blocks(str(exc))
            )
            return
        token = pending.put(
            PendingRewrite(
                text=text,
                tone=tone,
                argument=None,
                channel=channel,
                user=user,
                result_text=result.text,
            )
        )
        client.chat_postEphemeral(
            channel=channel,
            user=user,
            blocks=blocks.preview_blocks(token, result, tone),
        )

    @app.shortcut("proresponse_compose")
    def shortcut_compose(ack, shortcut, client):
        ack()
        user = shortcut["user"]["id"]
        client.views_open(
            trigger_id=shortcut["trigger_id"],
            view=blocks.compose_modal(prefs.get(user).tone),
        )

    # -- modal submission ----------------------------------------------
    @app.view("pr_compose_submit")
    def compose_submit(ack, body, view):
        text, tone = blocks.parse_compose_submission(view["state"])
        user = body["user"]["id"]
        if not text.strip():
            ack(
                response_action="errors",
                errors={"pr_compose_text": "Please enter a message to rewrite."},
            )
            return
        if not limiter.allow(user):
            ack(
                response_action="errors",
                errors={"pr_compose_text": "You're going a bit fast — try again shortly."},
            )
            return
        try:
            result = _run_rewrite(text, tone, user)
        except ValueError as exc:
            ack(response_action="errors", errors={"pr_compose_text": str(exc)})
            return
        except ProviderError as exc:
            ack(response_action="update", view=_error_view(str(exc)))
            return
        ack(
            response_action="update",
            view=blocks.compose_result_modal(result, tone),
        )

    return app


def main() -> int:
    """Entry point for ``proresponse slack`` and ``proresponse-slack``."""

    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not settings.slack_bot_token:
        log.error("SLACK_BOT_TOKEN is not set. See .env.example.")
        return 2

    try:
        app = build_app(settings)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 2

    if settings.slack_mode == "http":
        if not settings.slack_signing_secret:
            log.error("HTTP mode requires SLACK_SIGNING_SECRET.")
            return 2
        log.info("Starting Pro Response in HTTP mode on %s:%s", settings.host, settings.port)
        app.start(host=settings.host, port=settings.port)
        return 0

    # Default: Socket Mode.
    if not settings.slack_app_token:
        log.error("Socket Mode requires SLACK_APP_TOKEN (xapp-...). See .env.example.")
        return 2
    try:
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError as exc:  # pragma: no cover - dependency guard
        log.error("slack_bolt socket-mode adapter unavailable: %s", exc)
        return 2

    log.info("Starting Pro Response in Socket Mode (provider=%s, model=%s)",
             settings.provider, settings.model)
    SocketModeHandler(app, settings.slack_app_token).start()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
