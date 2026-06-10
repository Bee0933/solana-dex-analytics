from datetime import date, datetime

from prefect import task

from src.config.settings import settings
from src.sources.defillama import DefiLlamaParser
from src.utils.bigquery import (
    create_market_share_table_if_not_exists,
    delete_snapshot,
    get_bq_client,
    get_market_share_schema,
    load_rows,
    rows_exist_for_snapshot,
)
from src.utils.gcs import read_json_from_gcs
from src.utils.logging import get_logger

logger = get_logger(__name__)


@task(retries=0)
def load_market_share_to_bq(
    gcs_uri: str,
    snapshot_date: date,
    snapshot_at: datetime,
    overwrite: bool = False,
) -> int:
    client = get_bq_client(settings.gcp_project_id)
    create_market_share_table_if_not_exists(client, settings.bq_dataset_raw)
    table_ref = f"{client.project}.{settings.bq_dataset_raw}.raw_dex_market_share"

    dataset = settings.bq_dataset_raw
    if rows_exist_for_snapshot(client, dataset, "raw_dex_market_share", snapshot_date):
        if not overwrite:
            logger.info("load_market_share_skipped", snapshot_date=snapshot_date.isoformat())
            return 0
        deleted = delete_snapshot(client, dataset, "raw_dex_market_share", snapshot_date)
        logger.info("load_market_share_slice_deleted", deleted_rows=deleted)

    raw = read_json_from_gcs(gcs_uri)
    rows = DefiLlamaParser().parse(raw, snapshot_at, snapshot_date, gcs_uri)

    serialized = [
        {
            **row,
            "snapshot_at": row["snapshot_at"].isoformat(),
            "snapshot_date": row["snapshot_date"].isoformat(),
        }
        for row in rows
    ]

    rows_loaded, job_id = load_rows(client, table_ref, serialized, get_market_share_schema())
    logger.info(
        "load_market_share_complete",
        snapshot_date=snapshot_date.isoformat(),
        rows_loaded=rows_loaded,
        table=table_ref,
        job_id=job_id,
    )
    return rows_loaded
