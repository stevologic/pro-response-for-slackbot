"""Shared test doubles."""

from __future__ import annotations

from proresponse.providers.base import (
    LLMProvider,
    ProviderError,
    RewriteRequest,
    RewriteResult,
)


class FakeProvider(LLMProvider):
    """A provider that records requests and returns a canned rewrite.

    Set ``raise_error`` to make :meth:`rewrite` raise a
    :class:`ProviderError`, simulating a backend failure.
    """

    name = "fake"

    def __init__(self, reply: str = "REWRITTEN", *, raise_error: bool = False) -> None:
        self.reply = reply
        self.raise_error = raise_error
        self.requests: list[RewriteRequest] = []

    def rewrite(self, request: RewriteRequest) -> RewriteResult:
        self.requests.append(request)
        if self.raise_error:
            raise ProviderError("simulated failure")
        return RewriteResult(
            text=self.reply,
            model=request.model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 5},
        )
