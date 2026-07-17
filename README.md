<h1 align="center">Pro Response ✍️</h1>

<p align="center">
  <strong>An AI writing assistant for Slack.</strong><br>
  Rewrite, refine, and reformat your team's messages with modern LLMs — before you hit send.
</p>

<p align="center">
  <a href="https://github.com/stevologic/pro-response/actions"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/stevologic/pro-response/ci.yml?branch=main"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-2.0.0-blueviolet">
</p>

<p align="center">
  <a href="https://stevologic.github.io/pro-response/"><strong>🌐 Website</strong></a> ·
  <a href="docs/create_and_configure_slackbot.md">Slack setup</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

Pro Response is a Slack bot that polishes written communication. Ask it to fix
grammar, sound more professional, soften a tense message, translate, summarize,
or apply your own instruction — you preview the result and post it with one
click. Version 2.0 is a ground-up rewrite for 2026: a provider-agnostic model
layer (OpenAI, Anthropic, and any OpenAI-compatible endpoint), rich interactive
Slack UX, a local CLI, and a proper Python package.

## ✨ Highlights

- **14 tones** — professional, friendly, concise, expand, formal, casual,
  grammar-fix, soften, assertive, bullet points, summarize, simplify, add-emoji,
  translate, plus a **custom instruction** mode.
- **Any model** — OpenAI (GPT-5 / GPT-4.1 / GPT-4o / o-series, via the modern
  **Responses API**), Anthropic (Claude Opus 4.8, Sonnet 5, Haiku 4.5, Fable 5),
  or **any OpenAI-compatible host** (Azure OpenAI, Groq, OpenRouter, Together,
  Ollama, vLLM).
- **Interactive previews** — Post to channel · Regenerate · Change tone ·
  Discard, all from an ephemeral message only you can see.
- **Everywhere in Slack** — slash commands, a message shortcut (refine any
  message), a global compose modal, and an App Home tab with a per-user default
  tone.
- **Run it your way** — as a **Slack bot**, a standalone **HTTP JSON API**, or a
  **CLI / Python library** — one rewrite engine behind all three.
- **Slack: Socket Mode or HTTP** — run the bot with no public URL, or behind HTTPS.
- **Batteries included** — per-user rate limiting, a smart sanitizer that keeps
  code/links/mentions intact, a CLI, tests, CI, and Docker.

## 🚀 Quick start

```bash
git clone https://github.com/stevologic/pro-response.git
cd pro-response

python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[anthropic]"                        # drop [anthropic] for OpenAI-only

cp .env.example .env
# Fill in your model key (OPENAI_API_KEY) — plus, for Slack, SLACK_BOT_TOKEN + SLACK_APP_TOKEN

proresponse-slack     # run the Slack bot   (2-min setup guide below)
# ── or ──
proresponse-api       # run the HTTP JSON API instead — no Slack needed
```

Creating the Slack app takes about two minutes with the provided manifest — see
**[docs/create_and_configure_slackbot.md](docs/create_and_configure_slackbot.md)**.
For the API, jump to [HTTP API](#-http-api) below.

## 💬 Using it in Slack

| Action | What happens |
| --- | --- |
| `/pro can u send me teh report` | Rewrites with your default tone; shows a preview with buttons. |
| `/pro friendly can you review this?` | First word picks the tone inline. |
| `/prr fix this pls` | Returns a **private** recommendation only (legacy 1.x behavior). |
| Message → **Pro Response: rewrite** | Refine an existing message in place. |
| Global shortcut → **Compose with Pro Response** | Draft from scratch in a modal. |
| **App Home** | Read the help and set your default tone. |

From a preview you can **Post to channel**, **Regenerate**, switch tone, or
**Discard** — nothing is posted until you choose to.

## 🖥️ Command line

The same engine works in your terminal — handy for scripting or trying tones.

```bash
proresponse rewrite "hey can u send me teh report" --tone professional
echo "make this warmer" | proresponse rewrite --tone friendly
proresponse rewrite "good morning team" --tone translate --arg "Japanese"
proresponse tones                       # list every tone
proresponse models --provider anthropic # list known models
```

## 🌐 HTTP API

Prefer to call it from your own app or another service? Run the built-in JSON
API — no Slack required. It only needs a model provider key.

```bash
# install (OpenAI-only is enough), then run:
pip install -e ".[anthropic]"
proresponse serve                 # or the console script: proresponse-api
# → listening on http://0.0.0.0:3000  (override with --host/--port or SERVICE_IP/SERVICE_PORT)
```

| Method & path | Purpose |
| --- | --- |
| `GET /healthz` | Liveness check + the active provider/model. |
| `GET /tones` | List the available tones. |
| `POST /rewrite` | Rewrite text. Body: `{"text": "...", "tone": "friendly", "argument": null, "model": null}`. |

```bash
curl -s localhost:3000/rewrite \
  -H 'Content-Type: application/json' \
  -d '{"text":"hey can u fix teh report by eod","tone":"friendly"}'
# → {"text":"Hi! Could you fix the report by end of day? Thanks 🙂",
#     "tone":"friendly","model":"gpt-5-mini","provider":"openai","usage":{...}}
```

**Securing it:** set `PRO_API_KEY` to require `Authorization: Bearer <key>` on
`POST /rewrite` (`/healthz` stays open). The server is dependency-free (Python
stdlib); for heavy production traffic, put it behind a real WSGI/ASGI server or
use the library directly (below). Errors are JSON: `400` (bad input), `401`
(auth), `502` (provider), `404`/`405` (routing).

### Or embed it as a Python library

```python
from proresponse import get_provider
from proresponse.core import RewriteService

svc = RewriteService(provider=get_provider("openai"), model="gpt-5-mini")
print(svc.rewrite("make this friendlier pls", transform="friendly").text)
```

## ⚙️ Configuration

Everything is set via environment variables (see
[`.env.example`](.env.example)). The essentials:

| Variable | Default | Description |
| --- | --- | --- |
| `PRO_PROVIDER` | `openai` | `openai`, `anthropic`, or `openai-compatible`. |
| `PRO_MODEL` | provider default | e.g. `gpt-5-mini`, `claude-sonnet-5`. |
| `PRO_DEFAULT_TONE` | `professional` | Fallback tone. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | Provider credential. |
| `PRO_BASE_URL` | — | Endpoint for `openai-compatible` hosts. |
| `PRO_RATE_LIMIT_PER_MINUTE` | `20` | Per-user limit (`0` disables). |
| `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` | — | Slack credentials (Socket Mode). |
| `SLACK_MODE` | `socket` | Slack connection mode: `socket` or `http`. |
| `PRO_API_KEY` | — | If set, `POST /rewrite` (HTTP API) requires this bearer token. |
| `SERVICE_IP` / `SERVICE_PORT` | `0.0.0.0` / `3000` | Bind address/port for the API and Slack HTTP mode. |

### Using an OpenAI-compatible host

```bash
PRO_PROVIDER=openai-compatible
PRO_BASE_URL=https://api.groq.com/openai/v1
PRO_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=your-groq-key
```

## 🐳 Docker

```bash
cp .env.example .env      # fill in your tokens
docker compose up --build
```

Or plain Docker:

```bash
docker build -t pro-response .
docker run --env-file .env pro-response
```

## 🧩 Architecture

```
proresponse/
├── transforms.py        # the 14 tones (declarative)
├── sanitize.py          # input cleaning that preserves meaning
├── core.py              # sanitize → prompt → provider pipeline
├── ratelimit.py         # per-user token bucket
├── config.py            # env-driven Settings
├── cli.py               # `proresponse` command
├── server.py            # dependency-free HTTP JSON API
├── providers/           # OpenAI · Anthropic · OpenAI-compatible
│   ├── base.py          #   LLMProvider interface + dataclasses
│   ├── registry.py      #   known-model catalog
│   └── ...
└── slack/               # slack_bolt app, Block Kit, state
```

Adding a **tone** is a one-line entry in `transforms.py`; adding a **provider**
is one class plus a line in the factory. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## 🧪 Development

```bash
pip install -e ".[anthropic,dev]"
pytest                      # no network or API keys needed
ruff check proresponse tests
```

## 📸 Examples

![example](docs/examples/example1.PNG)
![example](docs/examples/example2.PNG)
![example](docs/examples/example3.PNG)

## 🤝 Contributing

Pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## ☕ Donate

Pro Response is free and MIT-licensed. If it saves you time, a tip helps keep it
improving — thank you! 🙏

<table>
  <tr>
    <th align="center">₿&nbsp; Bitcoin (BTC)</th>
    <th align="center">Ð&nbsp; Dogecoin (DOGE)</th>
  </tr>
  <tr>
    <td align="center"><img src="docs/donate/btc.png" alt="Bitcoin donation QR code" width="170"></td>
    <td align="center"><img src="docs/donate/doge.png" alt="Dogecoin donation QR code" width="170"></td>
  </tr>
</table>

Scan a QR code above, or copy an address below (hover the box and click the
copy icon):

**Bitcoin (BTC)**

```text
3M9PTxL15b6c8REcHMZCVPbfMomXNZ5AGR
```

**Dogecoin (DOGE)**

```text
DTW2M5oEW97WbmYJRM71qD7uE6xfJs1MUK
```

> Always confirm the address matches before sending — crypto transfers cannot be reversed.

## 📄 License

[MIT](LICENSE) © 2022-2026 Stephen M Abbott
