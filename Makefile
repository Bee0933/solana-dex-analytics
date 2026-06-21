.PHONY: install lint format run image run-image build

install:
	uv sync

lint:
	uv run ruff check src/
	uv run ruff format --check src/

format:
	uv run ruff format src/

run:
	uv run python -m src.pipeline

image:
	docker build --platform linux/amd64 -f docker/Dockerfile -t solana-pipeline:local .

run-image: image
	docker run --rm \
		--env-file .env \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json \
		-v "$$HOME/.config/gcloud/application_default_credentials.json":/tmp/adc.json:ro \
		solana-pipeline:local $(ARGS)

build:
	bash scripts/publish_image.sh
