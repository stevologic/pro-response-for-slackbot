from __future__ import annotations

from proresponse.providers.base import RewriteResult
from proresponse.slack import blocks
from proresponse.transforms import list_transforms


def _result() -> RewriteResult:
    return RewriteResult(
        text="Polished text.",
        model="gpt-5-mini",
        provider="openai",
        usage={"input_tokens": 10, "output_tokens": 4},
    )


def test_tone_options_cover_all_transforms():
    options = blocks.tone_options()
    assert len(options) == len(list_transforms())
    values = {o["value"] for o in options}
    assert "professional" in values


def test_preview_blocks_embed_token_in_block_id():
    view = blocks.preview_blocks("tok123", _result(), "friendly")
    actions = [b for b in view if b["type"] == "actions"][0]
    assert blocks.token_from_block_id(actions["block_id"]) == "tok123"
    action_ids = {e["action_id"] for e in actions["elements"]}
    assert blocks.ACTION_POST in action_ids
    assert blocks.ACTION_TONE in action_ids


def test_token_from_block_id_handles_bad_input():
    assert blocks.token_from_block_id(None) is None
    assert blocks.token_from_block_id("no-token-here") is None


def test_recommendation_blocks_include_original():
    view = blocks.recommendation_blocks("original message text", _result())
    joined = str(view)
    assert "original message text" in joined
    assert "Polished text." in joined


def test_home_view_is_home_type():
    view = blocks.home_view("professional")
    assert view["type"] == "home"
    assert any(b["type"] == "header" for b in view["blocks"])


def test_compose_modal_and_parse_roundtrip():
    modal = blocks.compose_modal("friendly")
    assert modal["callback_id"] == "pr_compose_submit"
    # Simulate a submitted view state.
    state = {
        "values": {
            "pr_compose_text": {"value": {"value": "hello world"}},
            "pr_compose_tone": {
                "value": {"selected_option": {"value": "concise"}}
            },
        }
    }
    text, tone = blocks.parse_compose_submission(state)
    assert text == "hello world"
    assert tone == "concise"
