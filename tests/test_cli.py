from __future__ import annotations

import proresponse.cli as cli
from tests.fakes import FakeProvider


def test_tones_command(capsys):
    assert cli.main(["tones"]) == 0
    out = capsys.readouterr().out
    assert "professional" in out
    assert "translate" in out


def test_models_command(capsys):
    assert cli.main(["models", "--provider", "openai"]) == 0
    out = capsys.readouterr().out
    assert "gpt-5-mini" in out
    assert "claude" not in out  # filtered to openai


def test_models_unknown_provider(capsys):
    assert cli.main(["models", "--provider", "nope"]) == 1


def test_rewrite_command(monkeypatch, capsys):
    fake = FakeProvider(reply="Cleaned up.")
    monkeypatch.setattr(cli, "get_provider", lambda *a, **k: fake)
    code = cli.main(["rewrite", "hey can u fix teh doc", "--tone", "friendly"])
    assert code == 0
    assert capsys.readouterr().out.strip() == "Cleaned up."
    # The transform reached the provider.
    assert "warm" in fake.requests[0].system_prompt.lower()


def test_rewrite_json_output(monkeypatch, capsys):
    fake = FakeProvider(reply="Done.")
    monkeypatch.setattr(cli, "get_provider", lambda *a, **k: fake)
    code = cli.main(["rewrite", "please tidy this message", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"text": "Done."' in out
    assert '"provider": "fake"' in out


def test_rewrite_empty_input_errors(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(cli, "get_provider", lambda *a, **k: fake)
    # Explicit empty string is too short; exit code 2.
    assert cli.main(["rewrite", ""]) == 2


def test_version_flag(capsys):
    try:
        cli.main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "proresponse" in out
