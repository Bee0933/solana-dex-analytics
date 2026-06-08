.PHONY: install test test-integration lint format clean help

install:
	uv sync

test:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest -m integration -v

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff format src/ tests/
