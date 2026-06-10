from datetime import date, datetime
from typing import Any

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from src.tasks.dbt_transform import run_dbt_build
from src.tasks.ingest_market_share import ingest_market_share
from src.tasks.ingest_pools import ingest_dex_pools
from src.tasks.load_market_share import load_market_share_to_bq
from src.tasks.load_pools import load_pools_to_bq
from src.utils.temporal import get_snapshot_metadata

POOL_DEXES = ["raydium", "orca", "meteora"]


@flow(name="solana-dex-daily", task_runner=ConcurrentTaskRunner(), log_prints=True)  # type: ignore[arg-type]
def solana_daily_flow(
    target_date: str | None = None,  # YYYY-MM-DD, defaults to yesterday
    dexes: list[str] | None = None,  # defaults to all three DEXs
    overwrite: bool = False,
    skip_dbt: bool = False,
    skip_market_share: bool = False,
) -> dict[str, Any]:
    logger = get_run_logger()

    _, yesterday = get_snapshot_metadata()
    run_date = date.fromisoformat(target_date) if target_date else yesterday
    run_dexes = dexes or POOL_DEXES
    logger.info(f"date={run_date}  dexes={run_dexes}")

    # pull raw data from all APIs at the same time
    pool_futures = {dex: ingest_dex_pools.submit(dex, run_date, overwrite) for dex in run_dexes}
    ms_future = ingest_market_share.submit(run_date, overwrite) if not skip_market_share else None

    pool_results = {dex: f.result() for dex, f in pool_futures.items()}
    ms_result = ms_future.result() if ms_future else None

    # load each raw file into BigQuery at the same time
    load_futures = {
        dex: load_pools_to_bq.submit(
            r["gcs_uri"], dex,
            date.fromisoformat(r["snapshot_date"]),
            datetime.fromisoformat(r["snapshot_at"]),
            overwrite,
        )
        for dex, r in pool_results.items()
    }
    ms_load = (
        load_market_share_to_bq.submit(
            ms_result["gcs_uri"],
            date.fromisoformat(ms_result["snapshot_date"]),
            datetime.fromisoformat(ms_result["snapshot_at"]),
            overwrite,
        )
        if ms_result else None
    )

    rows = {dex: f.result() for dex, f in load_futures.items()}
    rows["market_share"] = ms_load.result() if ms_load else 0
    logger.info(f"rows loaded: {rows}")

    # run dbt models
    dbt_result = run_dbt_build() if not skip_dbt else None

    return {
        "snapshot_date": run_date.isoformat(),
        "pool_ingestion": {dex: r["gcs_uri"] for dex, r in pool_results.items()},
        "market_share_ingestion": ms_result["gcs_uri"] if ms_result else None,
        "rows_loaded": rows,
        "dbt_summary": dbt_result,
    }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--date")
    p.add_argument("--dexes")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--skip-dbt", action="store_true")
    p.add_argument("--skip-market-share", action="store_true")
    a = p.parse_args()

    solana_daily_flow(
        target_date=a.date,
        dexes=a.dexes.split(",") if a.dexes else None,
        overwrite=a.overwrite,
        skip_dbt=a.skip_dbt,
        skip_market_share=a.skip_market_share,
    )
