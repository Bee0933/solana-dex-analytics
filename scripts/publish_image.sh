#!/usr/bin/env bash
# Builds the pipeline Docker image and pushes it to Artifact Registry (GCP image repo).
# The Cloud Run Job pulls this image to run the daily pipeline.
set -euo pipefail  # stop on any error, unset var, or failed pipe

# Prefer explicit env vars (set in CI/prod); fall back to local gcloud config.
REGION="${GCP_REGION:-europe-west3}"
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/solana-pipeline/solana-pipeline:latest"

# bail early with a clear message if no project is configured
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: no GCP project set. Set GCP_PROJECT_ID or run: gcloud config set project <id>"
  exit 1
fi

echo "Building and pushing $IMAGE"

# let docker authenticate to Artifact Registry using gcloud credentials
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# build for linux/amd64 (Cloud Run's arch) so it runs on Apple Silicon too
docker build --platform linux/amd64 -f docker/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"

echo "Done: $IMAGE"
