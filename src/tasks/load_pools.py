from datetime import date, datetime
from typing import Any

from prefect import task

from src.config.settings import settings
from src.sources.meteora import MeteoraParser
from src.sources.orca import OrcaParser
from src.sources.raydium import RaydiumParser
from src.utils.bigquery import (
    create_pools_table_if_not_exists,
    delete_snapshot,
    get_bq_client,
    get_pools_schema,
    load_rows,
    rows_exist_for_snapshot,
)
from src.utils.gcs import read_json_from_gcs
from src.utils.logging import get_logger

logger = get_logger(__name__)

_PARSER_REGISTRY: dict[str, Any] = {
    "raydium": RaydiumParser,
    "orca": OrcaParser,
    "meteora": MeteoraParser,
}


@task(retries=2, retry_delay_seconds=60)
def load_pools_to_bq(
    gcs_uri: str,
    dex: str,
    snapshot_date: date,
    snapshot_at: datetime,
    overwrite: bool = False,
) -> int:
    if dex not in _PARSER_REGISTRY:
        raise ValueError(f"dex must be one of {set(_PARSER_REGISTRY)}, got '{dex}'")

    client = get_bq_client(settings.gcp_project_id)
    create_pools_table_if_not_exists(client, settings.bq_dataset_raw)
    table_ref = f"{client.project}.{settings.bq_dataset_raw}.raw_dex_pools"

    dataset = settings.bq_dataset_raw
    if rows_exist_for_snapshot(client, dataset, "raw_dex_pools", snapshot_date, dex):
        if not overwrite:
            logger.info("load_pools_skipped", dex=dex, snapshot_date=snapshot_date.isoformat())
            return 0
        deleted = delete_snapshot(client, dataset, "raw_dex_pools", snapshot_date, dex)
        logger.info("load_pools_slice_deleted", dex=dex, deleted_rows=deleted)

    raw = read_json_from_gcs(gcs_uri)
    rows = _PARSER_REGISTRY[dex]().parse(raw, snapshot_at, snapshot_date, gcs_uri)

    # convert datetime/date objects to ISO strings before handing to BQ
    serialized = [
        {
            **row,
            "snapshot_at": row["snapshot_at"].isoformat(),
            "snapshot_date": row["snapshot_date"].isoformat(),
        }
        for row in rows
    ]

    rows_loaded, job_id = load_rows(client, table_ref, serialized, get_pools_schema())
    logger.info(
        "load_pools_complete",
        dex=dex,
        snapshot_date=snapshot_date.isoformat(),
        rows_loaded=rows_loaded,
        table=table_ref,
        job_id=job_id,
    )
    return rows_loaded
