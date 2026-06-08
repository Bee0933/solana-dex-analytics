# Solana DEX Analytics

A production-grade analytics data platform for Solana DEX activity, built on GCP using free public APIs.

## What it does

Ingests daily snapshots from three Solana DEX APIs (Raydium, Orca, Meteora) and the DefiLlama
market share feed, loads raw JSON into GCS, and transforms it through a Kimball-style dbt model
to answer two questions:

1. **LP visibility**: which pools are generating the best trailing returns across DEXs?
2. **DEX market share**: competitive positioning over time?

Data flows daily at 02:00 UTC: API → GCS raw lake → BigQuery raw tables → dbt (staging → marts) → Looker Studio.

## Architecture

```
Raydium / Orca / Meteora / DefiLlama   (free, unauthenticated APIs)
  └─ Prefect Cloud flow  (Cloud Run Job, 02:00 UTC)
       ├─ Task 1: Ingest — pull JSON, upload to GCS partitioned lake
       │    gs://solana-dex-raw/raw/dex_pools/dex={name}/date=YYYY-MM-DD/
       │    gs://solana-dex-raw/raw/dex_market_share/date=YYYY-MM-DD/
       ├─ Task 2: Load — stream GCS → BigQuery raw tables
       │    solana_raw.raw_dex_pools
       │    solana_raw.raw_dex_market_share
       └─ Task 3: Transform — dbt Core
            solana_staging → solana_intermediate → solana_marts
                                                       └─ Looker Studio
```

Every raw row carries `snapshot_at` (exact UTC call time) and `snapshot_date` (yesterday's date,
representing the rolling 24-hour window each API returns). Marts columns use `trailing_24h_*`
and `trailing_7d_*` prefixes — never `daily_*`.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | **3.10 exactly** | [python.org](https://python.org) or `pyenv install 3.10` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| gcloud CLI | latest | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |
| Terraform | ≥ 1.7 | [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform/install) |
| Docker | latest | [docs.docker.com](https://docs.docker.com/get-docker/) |

## Provisioning Infrastructure

All GCP resources are managed with Terraform. Run this once before the pipeline can execute.

**1. Create the Terraform state bucket manually** (one-time, before `terraform init`):

```bash
gsutil mb -p PROJECT_ID -l REGION gs://PROJECT_ID-tf-state
```

**2. Configure variables:**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project_id, region, github_repo, etc.
```

**3. Init, plan, apply:**

```bash
terraform init -backend-config="bucket=PROJECT_ID-tf-state"
terraform plan
terraform apply
```

**4. After apply** — store your Prefect API key in Secret Manager:

```bash
echo -n "YOUR_PREFECT_API_KEY" | \
  gcloud secrets versions add prefect-api-key --data-file=- --project=PROJECT_ID
```

## Local Setup

```bash
git clone <repo-url>
cd solana-dex-analytics
uv sync
uv run pre-commit install
cp .env.example .env   # then fill in your GCP values
gcloud auth application-default login
```

## Project Structure

```
solana-dex-analytics/
├── src/
│   ├── config/          # pydantic-settings (Settings, get_settings)
│   ├── sources/         # API clients — Raydium, Orca, Meteora, DefiLlama
│   ├── tasks/           # Prefect tasks (ingest, load, transform)
│   ├── flows/           # Prefect flow assembly
│   └── utils/           # logging, snapshots, GCS helpers, BQ helpers
├── dbt/                 # dbt Core project (staging → intermediate → marts)
├── terraform/           # GCP infrastructure as code
├── docker/              # Dockerfile for the Cloud Run job
├── tests/               # pytest — unit/ and integration/
└── scripts/             # local development helpers
```

## Implementation Stages

| Stage | Description | Status |
|-------|-------------|--------|
| 1 | Repo setup, tooling, folder skeleton | ✅ Done |
| 2 | Terraform — GCP infrastructure | ✅ Done |
| 3 | API clients and parsers (Raydium, Orca, Meteora, DefiLlama) | ⬜ |
| 4 | Prefect tasks and flow assembly | ⬜ |
| 5 | dbt models (staging → intermediate → marts) | ⬜ |
| 6 | Docker, Cloud Run, CI/CD | ⬜ |

## Cost Target

Under $5/month at portfolio scale — BigQuery on-demand free tier + Cloud Run scale-to-zero.
