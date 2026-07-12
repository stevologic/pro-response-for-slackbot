"""Block Kit builders for the Slack UI.

Keeping all the Block Kit JSON in one module means the app wiring in
``app.py`` reads as intent ("show the preview") rather than nested dict
literals. Every builder returns plain lists/dicts that ``slack_bolt`` accepts
directly.
"""

from __future__ import annotations

from proresponse.providers.base import RewriteResult
from proresponse.transforms import Transform, get_transform, list_transforms

__all__ = [
    "ACTION_POST",
    "ACTION_REGEN",
    "ACTION_DISCARD",
    "ACTION_TONE",
    "ACTION_HOME_TONE",
    "tone_options",
    "preview_blocks",
    "recommendation_blocks",
    "home_view",
    "compose_modal",
    "compose_result_modal",
    "error_blocks",
]

# Action ids — referenced from app.py so they stay in sync.
ACTION_POST = "pr_post"
ACTION_REGEN = "pr_regen"
ACTION_DISCARD = "pr_discard"
ACTION_TONE = "pr_tone"
ACTION_HOME_TONE = "home_set_tone"

# Block ids carry the pending token so selects (which have no free-form value)
# can still find their context.
_BLOCK_ACTIONS = "pr_actions"
_TOKEN_SEP = "::"


def _block_id_with_token(token: str) -> str:
    return f"{_BLOCK_ACTIONS}{_TOKEN_SEP}{token}"


def token_from_block_id(block_id: str | None) -> str | None:
    """Extract the pending token from an actions block id."""

    if not block_id or _TOKEN_SEP not in block_id:
        return None
    return block_id.split(_TOKEN_SEP, 1)[1]


def _tone_option(tf: Transform) -> dict:
    return {
        "text": {"type": "plain_text", "text": f":{tf.emoji}: {tf.label}"},
        "value": tf.key,
    }


def tone_options() -> list[dict]:
    """Static-select options for every transform."""

    return [_tone_option(tf) for tf in list_transforms()]


def _usage_context(result: RewriteResult) -> str:
    bits = [f"{result.provider} · {result.model}"]
    if result.usage:
        total = (result.usage.get("input_tokens", 0) or 0) + (
            result.usage.get("output_tokens", 0) or 0
        )
        if total:
            bits.append(f"{total} tokens")
    return "  ·  ".join(bits)


def preview_blocks(
    token: str, result: RewriteResult, tone_key: str
) -> list[dict]:
    """An interactive ephemeral preview with post/regenerate/tone/discard."""

    tf = get_transform(tone_key)
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Pro Response* — :{tf.emoji}: _{tf.label}_ preview",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": result.text},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": _usage_context(result)},
            ],
        },
        {
            "type": "actions",
            "block_id": _block_id_with_token(token),
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Post to channel"},
                    "style": "primary",
                    "action_id": ACTION_POST,
                    "value": token,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Regenerate"},
                    "action_id": ACTION_REGEN,
                    "value": token,
                },
                {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Change tone"},
                    "action_id": ACTION_TONE,
                    "options": tone_options(),
                    "initial_option": _tone_option(tf),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Discard"},
                    "style": "danger",
                    "action_id": ACTION_DISCARD,
                    "value": token,
                },
            ],
        },
    ]


def recommendation_blocks(original: str, result: RewriteResult) -> list[dict]:
    """A plain, non-interactive ephemeral recommendation (legacy ``/prr``)."""

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Recommendation* ({result.provider} · {result.model})",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": result.text}},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"_Original:_ {original[:280]}"},
            ],
        },
    ]


def error_blocks(message: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":warning: {message}"},
        }
    ]


def home_view(default_tone: str) -> dict:
    """The App Home tab: help + a default-tone picker."""

    tf = get_transform(default_tone)
    tone_lines = "\n".join(
        f":{t.emoji}: *{t.label}* — {t.description}" for t in list_transforms()
    )
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Pro Response ✍️"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "I polish your messages before you send them — fixing "
                        "grammar and reshaping tone with modern AI models.\n\n"
                        "*How to use me*\n"
                        "• `/pro <message>` — preview a rewrite, then post it\n"
                        "• `/pro <tone> <message>` — pick a tone inline "
                        "(e.g. `/pro friendly can u fix this`)\n"
                        "• `/prr <message>` — get a private recommendation only\n"
                        "• Message shortcut *Pro Response: rewrite* — refine any "
                        "existing message\n"
                        "• Global shortcut *Compose with Pro Response* — draft "
                        "from scratch"
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Your default tone:* :{tf.emoji}: {tf.label}",
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": ACTION_HOME_TONE,
                    "placeholder": {"type": "plain_text", "text": "Set default"},
                    "options": tone_options(),
                    "initial_option": _tone_option(tf),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Available tones*\n{tone_lines}"},
            },
        ],
    }


# Modal for the global "compose" shortcut.
_COMPOSE_CALLBACK = "pr_compose_submit"
_COMPOSE_TEXT_BLOCK = "pr_compose_text"
_COMPOSE_TEXT_ACTION = "value"
_COMPOSE_TONE_BLOCK = "pr_compose_tone"
_COMPOSE_TONE_ACTION = "value"


def compose_modal(default_tone: str) -> dict:
    """A modal with a text area and a tone picker."""

    tf = get_transform(default_tone)
    return {
        "type": "modal",
        "callback_id": _COMPOSE_CALLBACK,
        "title": {"type": "plain_text", "text": "Pro Response"},
        "submit": {"type": "plain_text", "text": "Rewrite"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": _COMPOSE_TEXT_BLOCK,
                "label": {"type": "plain_text", "text": "Your message"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": _COMPOSE_TEXT_ACTION,
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Type or paste the message to refine…",
                    },
                },
            },
            {
                "type": "input",
                "block_id": _COMPOSE_TONE_BLOCK,
                "label": {"type": "plain_text", "text": "Tone"},
                "element": {
                    "type": "static_select",
                    "action_id": _COMPOSE_TONE_ACTION,
                    "options": tone_options(),
                    "initial_option": _tone_option(tf),
                },
            },
        ],
    }


def compose_result_modal(result: RewriteResult, tone_key: str) -> dict:
    """The compose modal, updated in place to show the rewrite."""

    tf = get_transform(tone_key)
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Pro Response"},
        "close": {"type": "plain_text", "text": "Done"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":{tf.emoji}: *{tf.label}* rewrite:",
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": result.text}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "Copy the text above. "
                            f"_{result.provider} · {result.model}_"
                        ),
                    }
                ],
            },
        ],
    }


def parse_compose_submission(view_state: dict) -> tuple[str, str]:
    """Pull (text, tone) out of a submitted compose modal's state."""

    values = view_state.get("values", {})
    text = (
        values.get(_COMPOSE_TEXT_BLOCK, {})
        .get(_COMPOSE_TEXT_ACTION, {})
        .get("value", "")
        or ""
    )
    tone = (
        values.get(_COMPOSE_TONE_BLOCK, {})
        .get(_COMPOSE_TONE_ACTION, {})
        .get("selected_option", {})
        or {}
    ).get("value", "professional")
    return text, tone
