# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

LABEL org.opencontainers.image.title="pro-response" \
      org.opencontainers.image.description="An AI writing assistant for Slack." \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml requirements.txt README.md ./
COPY proresponse ./proresponse

# Install the package with the Anthropic provider available.
RUN pip install --upgrade pip && pip install ".[anthropic]"

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Socket Mode needs no inbound port; expose the HTTP-mode port for convenience.
EXPOSE 3000

ENTRYPOINT ["proresponse-slack"]
