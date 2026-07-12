.PHONY: help install dev test lint fmt run docker clean

help:
	@echo "Targets:"
	@echo "  install   Install the package"
	@echo "  dev       Install with dev + anthropic extras (editable)"
	@echo "  test      Run the test suite"
	@echo "  lint      Run ruff"
	@echo "  fmt       Auto-fix with ruff"
	@echo "  run       Start the Slack bot"
	@echo "  docker    Build the Docker image"
	@echo "  clean     Remove caches and build artifacts"

install:
	pip install .

dev:
	pip install -e ".[anthropic,dev]"

test:
	pytest

lint:
	ruff check proresponse tests

fmt:
	ruff check --fix proresponse tests

run:
	proresponse-slack

docker:
	docker build -t pro-response-for-slackbot:2.0.0 .

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
