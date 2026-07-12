# Changelog

All notable changes to Pro Response are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-07-12

A ground-up rewrite for 2026. Same idea — polish your team's messages before
they go out — with a modern architecture and far more capability.

### Added
- **Multi-provider model layer.** OpenAI (default), Anthropic (Claude), and any
  OpenAI-compatible endpoint (Azure OpenAI, Groq, OpenRouter, Together, Ollama,
  vLLM) behind one interface. Pick provider and model via configuration.
- **A data-driven model registry** covering current OpenAI and Anthropic models
  (GPT-5 family, GPT-4.1, GPT-4o, o-series; Claude Opus 4.8, Sonnet 5, Haiku
  4.5, Fable 5) — with any unlisted id still accepted.
- **Fourteen tones/transforms:** professional, friendly, concise, expand,
  formal, casual, grammar-only, soften, assertive, bullet points, summarize,
  simplify, add-emoji, translate, and a custom-instruction mode.
- **Rich Slack UX** on `slack_bolt`: interactive previews (Post / Regenerate /
  Change-tone / Discard), a message shortcut, a global compose modal, and an
  App Home tab with a per-user default-tone picker.
- **Socket Mode and HTTP Mode**, per-user rate limiting, and a much smarter
  input sanitizer that preserves punctuation, code, links, and mentions.
- **A local CLI** (`proresponse`) for rewriting from the terminal, plus
  `proresponse-slack` to run the bot.
- Tests, GitHub Actions CI, a modern Dockerfile, Docker Compose, and a
  GitHub Pages landing site.

### Changed
- Replaced the removed OpenAI Completions endpoint (`text-davinci-003`) with the
  modern Responses API (and Chat Completions fallback).
- Restructured the loose `src/` scripts into an installable `proresponse`
  package with a clean provider/transform/Slack separation.

### Removed
- The Flask web service and the old `/pr`, `/prr` raw-endpoint wiring. The `/pr`
  and `/prr` slash commands remain, now backed by the new pipeline.
