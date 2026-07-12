# Contributing to Pro Response

Thanks for your interest! Contributions of all sizes are welcome.

## Development setup

```bash
git clone https://github.com/stevologic/pro-response.git
cd pro-response
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[anthropic,dev]"
```

## Running the checks

```bash
pytest              # tests (no network or API keys required)
ruff check proresponse tests
```

The test suite uses fake providers, so it never makes network calls.

## Adding a new tone

Tones live in [`proresponse/transforms.py`](proresponse/transforms.py). Add one
entry to the `_ALL` tuple with a key, label, emoji, description, and
instruction — that's the whole change. It automatically appears in the CLI,
the Slack menus, the App Home tab, and the docs.

## Adding a new provider

Implement `LLMProvider` in `proresponse/providers/`, register it in
`proresponse/providers/__init__.py:get_provider`, and add any known model ids to
`registry.py`. Keep SDK imports lazy so unrelated providers don't pull in
dependencies they don't need.

## Pull requests

- Keep changes focused and covered by tests.
- Run `ruff` and `pytest` before opening the PR.
- Describe the behavior change and any new configuration in the PR body.
