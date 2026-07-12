"""A small, dependency-free HTTP JSON API for Pro Response.

This lets you use the same rewrite engine outside of Slack — from a web app, a
script, another service, or curl. It is built on the standard library
(``http.server``), so it adds no dependencies; for high-traffic production use
put it behind a real WSGI/ASGI server or call :mod:`proresponse.core` directly.

Endpoints
---------
* ``GET  /healthz`` — liveness plus the active provider/model.
* ``GET  /tones``   — the list of available tones.
* ``POST /rewrite`` — ``{"text": "...", "tone": "professional",
  "argument": null, "model": null}`` → the rewritten text plus metadata.

Auth
----
If ``PRO_API_KEY`` is set, ``POST /rewrite`` requires an
``Authorization: Bearer <key>`` header. ``/healthz`` is always open.

The request handling is split into a pure :func:`process_request` function
(easily unit-tested without sockets) and a thin :class:`BaseHTTPRequestHandler`
that adapts it to the socket server.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from proresponse.core import ProviderError, RewriteService
from proresponse.transforms import list_transforms

log = logging.getLogger(__name__)

__all__ = ["process_request", "make_handler", "serve", "main"]


def _tones_payload() -> dict:
    return {
        "tones": [
            {
                "key": t.key,
                "label": t.label,
                "description": t.description,
                "takes_argument": t.takes_argument,
            }
            for t in list_transforms()
        ]
    }


def process_request(
    *,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    service: RewriteService,
    default_tone: str,
    provider_name: str,
    api_key: str | None = None,
) -> tuple[int, dict]:
    """Handle one API request and return ``(status_code, json_payload)``.

    ``headers`` must be a mapping with lowercased keys. This function performs
    no I/O, which makes it straightforward to test.
    """

    # Strip any query string; normalize trailing slash.
    route = path.split("?", 1)[0].rstrip("/") or "/"

    if method == "GET" and route in ("/", "/healthz"):
        return 200, {
            "status": "ok",
            "provider": provider_name,
            "model": service.model,
        }

    if method == "GET" and route == "/tones":
        return 200, _tones_payload()

    if route == "/rewrite":
        if method != "POST":
            return 405, {"error": "Use POST for /rewrite."}

        if api_key:
            auth = headers.get("authorization", "")
            if auth != f"Bearer {api_key}":
                return 401, {"error": "Missing or invalid API key."}

        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, UnicodeDecodeError):
            return 400, {"error": "Request body must be valid JSON."}
        if not isinstance(data, dict):
            return 400, {"error": "Request body must be a JSON object."}

        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return 400, {"error": "Field 'text' is required."}

        tone = data.get("tone") or default_tone
        argument = data.get("argument")
        model = data.get("model")

        try:
            result = service.rewrite(
                text, transform=tone, argument=argument, model=model
            )
        except ValueError as exc:  # too-short input, etc.
            return 400, {"error": str(exc)}
        except ProviderError as exc:
            return 502, {"error": str(exc)}
        except Exception:  # noqa: BLE001 - last-resort guard
            log.exception("Unexpected error handling /rewrite")
            return 500, {"error": "Internal server error."}

        return 200, {
            "text": result.text,
            "tone": tone,
            "model": result.model,
            "provider": result.provider,
            "usage": result.usage,
        }

    return 404, {"error": "Not found."}


def make_handler(
    service: RewriteService,
    *,
    default_tone: str,
    provider_name: str,
    api_key: str | None,
):
    """Build a request-handler class bound to ``service`` and settings."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "ProResponse"

        # Silence the default noisy stderr logging; route through our logger.
        def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
            log.info("%s - %s", self.address_string(), fmt % args)

        def _dispatch(self, method: str) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length > 0 else b""
                lower_headers = {k.lower(): v for k, v in self.headers.items()}
                status, payload = process_request(
                    method=method,
                    path=self.path,
                    body=body,
                    headers=lower_headers,
                    service=service,
                    default_tone=default_tone,
                    provider_name=provider_name,
                    api_key=api_key,
                )
            except Exception:  # noqa: BLE001 - never crash the handler thread
                log.exception("Unhandled error in request handler")
                status, payload = 500, {"error": "Internal server error."}

            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionError):  # client disconnected
                pass

        def do_GET(self):  # noqa: N802 - stdlib naming
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802 - stdlib naming
            self._dispatch("POST")

    return Handler


def serve(settings, *, host: str | None = None, port: int | None = None) -> int:
    """Run the HTTP API server (blocking) using ``settings``.

    Args:
        settings: A :class:`proresponse.config.Settings`.
        host: Bind address; defaults to ``settings.host``.
        port: Bind port; defaults to ``settings.port``.
    """

    service = RewriteService(
        provider=settings.build_provider(),
        model=settings.model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        max_input_chars=settings.max_input_chars,
    )
    handler = make_handler(
        service,
        default_tone=settings.default_transform,
        provider_name=settings.provider,
        api_key=settings.api_key,
    )
    bind_host = host or settings.host
    bind_port = port or settings.port
    httpd = ThreadingHTTPServer((bind_host, bind_port), handler)
    log.info(
        "Pro Response API listening on http://%s:%s (provider=%s, model=%s)",
        bind_host,
        bind_port,
        settings.provider,
        settings.model,
    )
    if settings.api_key:
        log.info("API key auth is ENABLED for POST /rewrite.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual stop
        log.info("Shutting down.")
    finally:
        httpd.server_close()
    return 0


def main() -> int:  # pragma: no cover - process entry point
    """Entry point for ``proresponse-api``: run the API from the environment."""

    from proresponse.config import Settings

    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return serve(settings)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
