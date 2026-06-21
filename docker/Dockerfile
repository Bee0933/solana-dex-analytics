# syntax=docker/dockerfile:1.7
FROM python:3.10-slim AS builder

# use uv's prebuilt binary instead of `pip install uv` — faster and version-pinned
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
# cache mount keeps downloaded wheels (pyarrow, numpy, …) across builds for fast rebuilds.
# --no-install-project installs only dependencies; app code is copied into the runtime stage.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


FROM python:3.10-slim AS runtime

# python:slim already ships ca-certificates (for HTTPS), so no apt step is needed
RUN useradd --uid 1000 --create-home pipeline

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ /app/src/
COPY --chown=pipeline:pipeline dbt/ /app/dbt/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DBT_PROFILES_DIR=/app/dbt

USER pipeline

ENTRYPOINT ["python", "-m", "src.pipeline"]
