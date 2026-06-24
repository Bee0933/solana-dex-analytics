"""Daily Solana DEX pipeline: extract -> GCS lake -> BigQuery -> dbt.

Run as a one-shot job:  python -m src.pipeline [--date YYYY-MM-DD] [--overwrite] ...
Designed to run as a single Cloud Run Job, triggered daily by Cloud Scheduler.
"""

import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import sources
from src.bigquery import (
    create_market_share_table_if_not_exists,
    create_pools_table_if_not_exists,
    delete_snapshot,
    get_bq_client,
    get_market_share_schema,
    get_pools_schema,
    load_rows,
    rows_exist_for_snapshot,
)
from src.config import settings
from src.gcs import (
    build_market_share_partition_path,
    build_pool_partition_path,
    check_object_exists,
    get_object_metadata,
    read_json_from_gcs,
    write_json_to_gcs,
)
from src.logging import bind_context, configure_logging, get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).parents[1]
POOL_DEXES = ["raydium", "orca", "meteora"]

_POOL_FETCHERS = {
    "raydium": sources.fetch_raydium,
    "orca": sources.fetch_orca,
    "meteora": sources.fetch_meteora,
}
_POOL_PARSERS = {
    "raydium": sources.parse_raydium,
    "orca": sources.parse_orca,
    "meteora": sources.parse_meteora,
}


def get_snapshot_metadata() -> tuple[datetime, date]:
    """Return (snapshot_at UTC now, snapshot_date yesterday).

    snapshot_date is the 24h window the API data covers — always the prior day.
    """
    snapshot_at = datetime.now(timezone.utc)
    return snapshot_at, (snapshot_at - timedelta(days=1)).date()


# Extract: API -> GCS raw lake
def extract_pools(dex: str, run_date: date, snapshot_at: datetime, overwrite: bool) -> datetime:
    """Fetch a DEX's pools and land the raw JSON in GCS. Returns the snapshot_at to load with."""
    bucket = settings.gcs_bucket_name
    object_path = build_pool_partition_path(dex, run_date)
    gcs_uri = f"gs://{bucket}/{object_path}"

    if not overwrite and check_object_exists(bucket, object_path):
        existing = get_object_metadata(bucket, object_path)
        logger.info("extract_pools_skipped", dex=dex, gcs_uri=gcs_uri)
        return datetime.fromisoformat(existing.get("snapshot_at", snapshot_at.isoformat()))

    raw = _POOL_FETCHERS[dex]()
    record_count = len(raw.get("pools", []))
    write_json_to_gcs(
        bucket,
        object_path,
        raw,
        overwrite=overwrite,
        metadata={
            "snapshot_at": snapshot_at.isoformat(),
            "dex_name": dex,
            "snapshot_date": run_date.isoformat(),
            "raw_record_count": str(record_count),
        },
    )
    logger.info("extract_pools_complete", dex=dex, gcs_uri=gcs_uri, raw_record_count=record_count)
    return snapshot_at


def extract_market_share(run_date: date, snapshot_at: datetime, overwrite: bool) -> datetime:
    bucket = settings.gcs_bucket_name
    object_path = build_market_share_partition_path(run_date)
    gcs_uri = f"gs://{bucket}/{object_path}"

    if not overwrite and check_object_exists(bucket, object_path):
        existing = get_object_metadata(bucket, object_path)
        logger.info("extract_market_share_skipped", gcs_uri=gcs_uri)
        return datetime.fromisoformat(existing.get("snapshot_at", snapshot_at.isoformat()))

    raw = sources.fetch_market_share()
    write_json_to_gcs(
        bucket,
        object_path,
        raw,
        overwrite=overwrite,
        metadata={
            "snapshot_at": snapshot_at.isoformat(),
            "snapshot_date": run_date.isoformat(),
            "dex_count": str(len(raw.get("protocols", []))),
        },
    )
    logger.info("extract_market_share_complete", gcs_uri=gcs_uri)
    return snapshot_at


# Load: GCS raw lake -> BigQuery (idempotent per snapshot_date)
def _serialize(rows: list[dict]) -> list[dict]:
    # BQ JSON load needs ISO strings, not date/datetime objects
    return [
        {
            **row,
            "snapshot_at": row["snapshot_at"].isoformat(),
            "snapshot_date": row["snapshot_date"].isoformat(),
        }
        for row in rows
    ]


def load_pools(dex: str, run_date: date, snapshot_at: datetime, overwrite: bool) -> int:
    client = get_bq_client(settings.gcp_project_id)
    create_pools_table_if_not_exists(client, settings.bq_dataset_raw)
    dataset = settings.bq_dataset_raw
    table_ref = f"{client.project}.{dataset}.raw_dex_pools"

    # idempotent: skip if this day's data is already loaded, unless overwriting
    if rows_exist_for_snapshot(client, dataset, "raw_dex_pools", run_date, dex):
        if not overwrite:
            logger.info("load_pools_skipped", dex=dex, snapshot_date=run_date.isoformat())
            return 0
        deleted = delete_snapshot(client, dataset, "raw_dex_pools", run_date, dex)
        logger.info("load_pools_slice_deleted", dex=dex, deleted_rows=deleted)

    gcs_uri = f"gs://{settings.gcs_bucket_name}/{build_pool_partition_path(dex, run_date)}"
    raw = read_json_from_gcs(gcs_uri)
    rows = _POOL_PARSERS[dex](raw, snapshot_at, run_date, gcs_uri)
    rows_loaded, job_id = load_rows(client, table_ref, _serialize(rows), get_pools_schema())
    logger.info("load_pools_complete", dex=dex, rows_loaded=rows_loaded, job_id=job_id)
    return rows_loaded


def load_market_share(run_date: date, snapshot_at: datetime, overwrite: bool) -> int:
    client = get_bq_client(settings.gcp_project_id)
    create_market_share_table_if_not_exists(client, settings.bq_dataset_raw)
    dataset = settings.bq_dataset_raw
    table_ref = f"{client.project}.{dataset}.raw_dex_market_share"

    if rows_exist_for_snapshot(client, dataset, "raw_dex_market_share", run_date):
        if not overwrite:
            logger.info("load_market_share_skipped", snapshot_date=run_date.isoformat())
            return 0
        deleted = delete_snapshot(client, dataset, "raw_dex_market_share", run_date)
        logger.info("load_market_share_slice_deleted", deleted_rows=deleted)

    gcs_uri = f"gs://{settings.gcs_bucket_name}/{build_market_share_partition_path(run_date)}"
    raw = read_json_from_gcs(gcs_uri)
    rows = sources.parse_market_share(raw, snapshot_at, run_date, gcs_uri)
    rows_loaded, job_id = load_rows(client, table_ref, _serialize(rows), get_market_share_schema())
    logger.info("load_market_share_complete", rows_loaded=rows_loaded, job_id=job_id)
    return rows_loaded


# Transform: dbt build (staging -> intermediate -> marts)
def run_dbt(target: str = "dev") -> None:
    # pass GCP auth/project through to the dbt subprocess
    env = {**os.environ}
    if settings.google_application_credentials:
        env["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    if settings.gcp_project_id:
        env["GCP_PROJECT_ID"] = settings.gcp_project_id

    # install packages first (dbt deps), then run all models/tests (dbt build)
    for args in (["deps"], ["build", "--target", target]):
        cmd = ["dbt", *args, "--project-dir", "dbt", "--profiles-dir", "dbt"]
        logger.info("dbt_starting", cmd=" ".join(cmd))
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=str(_REPO_ROOT), env=env
        )
        for line in result.stdout.splitlines():
            if line.strip():
                logger.info("dbt", line=line)
        if result.returncode != 0:
            tail = "\n".join(result.stdout.splitlines()[-50:])
            raise RuntimeError(f"dbt {args[0]} exited with code {result.returncode}\n{tail}")
    logger.info("dbt_build_complete")


# Orchestrator
def run_pipeline(
    target_date: str | None = None,
    dexes: list[str] | None = None,
    overwrite: bool = False,
    skip_dbt: bool = False,
    skip_market_share: bool = False,
) -> None:
    """Run the full daily pipeline. Defaults to yesterday's data and all DEXs."""
    snapshot_at, yesterday = get_snapshot_metadata()
    run_date = date.fromisoformat(target_date) if target_date else yesterday
    run_dexes = dexes or POOL_DEXES
    bind_context(snapshot_date=run_date.isoformat())
    logger.info("pipeline_start", date=run_date.isoformat(), dexes=run_dexes)

    rows: dict[str, int] = {}
    failures: list[str] = []

    # Each source is isolated: if one API is down, the others still load and dbt
    # still runs. Failures are collected and reported at the end.
    for dex in run_dexes:
        try:
            extract_pools(dex, run_date, snapshot_at, overwrite)
            rows[dex] = load_pools(dex, run_date, snapshot_at, overwrite)
        except Exception as exc:
            logger.error("source_failed", source=dex, error=str(exc))
            failures.append(dex)

    if not skip_market_share:
        try:
            extract_market_share(run_date, snapshot_at, overwrite)
            rows["market_share"] = load_market_share(run_date, snapshot_at, overwrite)
        except Exception as exc:
            logger.error("source_failed", source="market_share", error=str(exc))
            failures.append("market_share")

    logger.info("rows_loaded", **rows)

    # dbt transforms whatever made it into BigQuery (and runs data-quality tests)
    if not skip_dbt:
        run_dbt()

    if failures:
        logger.error("pipeline_completed_with_failures", failed=failures)
        raise SystemExit(1)  # non-zero so Cloud Run marks the run failed + alerts
    logger.info("pipeline_complete", date=run_date.isoformat())


if __name__ == "__main__":
    # this block is what Cloud Run executes (see Dockerfile ENTRYPOINT)
    import argparse

    configure_logging(settings.log_level)

    p = argparse.ArgumentParser()
    p.add_argument("--date")  # YYYY-MM-DD; defaults to yesterday
    p.add_argument("--dexes")  # comma-separated; defaults to all three
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--skip-dbt", action="store_true")
    p.add_argument("--skip-market-share", action="store_true")
    a = p.parse_args()

    run_pipeline(
        target_date=a.date,
        dexes=a.dexes.split(",") if a.dexes else None,
        overwrite=a.overwrite,
        skip_dbt=a.skip_dbt,
        skip_market_share=a.skip_market_share,
    )
