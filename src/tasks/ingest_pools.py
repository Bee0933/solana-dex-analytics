from datetime import date
from typing import Any

from prefect import task

from src.config.settings import settings
from src.sources.meteora import MeteoraClient
from src.sources.orca import OrcaClient
from src.sources.raydium import RaydiumClient
from src.utils.gcs import (
    build_pool_partition_path,
    check_object_exists,
    get_object_metadata,
    write_json_to_gcs,
)
from src.utils.logging import get_logger
from src.utils.temporal import get_snapshot_metadata

logger = get_logger(__name__)

_CLIENT_REGISTRY: dict[str, Any] = {
    "raydium": RaydiumClient,
    "orca": OrcaClient,
    "meteora": MeteoraClient,
}


@task(retries=2, retry_delay_seconds=60)
def ingest_dex_pools(
    dex: str,
    snapshot_date: date | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    if dex not in _CLIENT_REGISTRY:
        raise ValueError(f"dex must be one of {set(_CLIENT_REGISTRY)}, got '{dex}'")

    snapshot_at, default_date = get_snapshot_metadata()
    resolved_date = snapshot_date if snapshot_date is not None else default_date

    bucket = settings.gcs_bucket_name
    object_path = build_pool_partition_path(dex, resolved_date)
    gcs_uri = f"gs://{bucket}/{object_path}"

    if not overwrite and check_object_exists(bucket, object_path):
        existing = get_object_metadata(bucket, object_path)
        logger.info(
            "ingest_pools_skipped",
            dex=dex,
            snapshot_date=resolved_date.isoformat(),
            gcs_uri=gcs_uri,
        )
        return {
            "dex": dex,
            "gcs_uri": gcs_uri,
            "snapshot_at": existing.get("snapshot_at", snapshot_at.isoformat()),
            "snapshot_date": resolved_date.isoformat(),
            "raw_record_count": int(existing.get("raw_record_count", 0)),
        }

    client = _CLIENT_REGISTRY[dex]()
    raw = client.fetch()
    record_count = len(raw.get("pools", []))

    obj_metadata: dict[str, str] = {
        "snapshot_at": snapshot_at.isoformat(),
        "dex_name": dex,
        "snapshot_date": resolved_date.isoformat(),
        "raw_record_count": str(record_count),
    }

    write_json_to_gcs(
        bucket_name=bucket,
        object_path=object_path,
        data=raw,
        overwrite=overwrite,
        metadata=obj_metadata,
    )

    logger.info(
        "ingest_pools_complete",
        dex=dex,
        snapshot_date=resolved_date.isoformat(),
        snapshot_at=snapshot_at.isoformat(),
        raw_record_count=record_count,
        gcs_uri=gcs_uri,
    )

    return {
        "dex": dex,
        "gcs_uri": gcs_uri,
        "snapshot_at": snapshot_at.isoformat(),
        "snapshot_date": resolved_date.isoformat(),
        "raw_record_count": record_count,
    }
