.PHONY: install lint format run build

install:
	uv sync

lint:
	uv run ruff check src/
	uv run ruff format --check src/

format:
	uv run ruff format src/

run:
	uv run python -m src.pipeline

build:
	bash scripts/publish_image.sh
