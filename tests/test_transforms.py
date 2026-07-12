from __future__ import annotations

from proresponse.transforms import (
    DEFAULT_TRANSFORM,
    build_system_prompt,
    get_transform,
    is_transform,
    list_transforms,
)


def test_default_transform_exists():
    assert get_transform(None).key == DEFAULT_TRANSFORM
    assert get_transform("").key == DEFAULT_TRANSFORM


def test_unknown_falls_back_to_default():
    assert get_transform("nonsense").key == DEFAULT_TRANSFORM


def test_alias_resolution():
    assert get_transform("tldr").key == "concise"
    assert get_transform("proofread").key == "grammar"
    assert get_transform("eli5").key == "simplify"


def test_is_transform_strict():
    assert is_transform("friendly") is True
    assert is_transform("tldr") is True
    assert is_transform("nonsense") is False
    assert is_transform("") is False
    assert is_transform(None) is False


def test_list_has_expected_members():
    keys = {t.key for t in list_transforms()}
    for expected in ("professional", "friendly", "grammar", "translate", "custom"):
        assert expected in keys


def test_build_system_prompt_includes_instruction():
    tf = get_transform("friendly")
    prompt = build_system_prompt(tf)
    assert "warm" in prompt.lower()
    assert "Pro Response" in prompt


def test_translate_argument_is_interpolated():
    tf = get_transform("translate")
    prompt = build_system_prompt(tf, "Spanish")
    assert "Spanish" in prompt


def test_custom_argument_is_interpolated():
    tf = get_transform("custom")
    prompt = build_system_prompt(tf, "make it rhyme")
    assert "make it rhyme" in prompt


def test_argument_transforms_survive_missing_argument():
    tf = get_transform("translate")
    # Should not raise even without an argument.
    prompt = build_system_prompt(tf, None)
    assert "Translate" in prompt
