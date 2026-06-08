from datetime import date
from typing import Any

from prefect import task

from src.config.settings import settings
from src.sources.defillama import DefiLlamaClient
from src.utils.gcs import (
    build_market_share_partition_path,
    check_object_exists,
    get_object_metadata,
    write_json_to_gcs,
)
from src.utils.logging import get_logger
from src.utils.temporal import get_snapshot_metadata

logger = get_logger(__name__)


@task(retries=2, retry_delay_seconds=60)
def ingest_market_share(
    snapshot_date: date | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    snapshot_at, default_date = get_snapshot_metadata()
    resolved_date = snapshot_date if snapshot_date is not None else default_date

    bucket = settings.gcs_bucket_name
    object_path = build_market_share_partition_path(resolved_date)
    gcs_uri = f"gs://{bucket}/{object_path}"

    if not overwrite and check_object_exists(bucket, object_path):
        existing = get_object_metadata(bucket, object_path)
        logger.info(
            "ingest_market_share_skipped",
            snapshot_date=resolved_date.isoformat(),
            gcs_uri=gcs_uri,
        )
        return {
            "gcs_uri": gcs_uri,
            "snapshot_at": existing.get("snapshot_at", snapshot_at.isoformat()),
            "snapshot_date": resolved_date.isoformat(),
            "dex_count": int(existing.get("dex_count", 0)),
        }

    client = DefiLlamaClient()
    raw = client.fetch()
    dex_count = len(raw.get("protocols", []))

    obj_metadata: dict[str, str] = {
        "snapshot_at": snapshot_at.isoformat(),
        "snapshot_date": resolved_date.isoformat(),
        "dex_count": str(dex_count),
    }

    write_json_to_gcs(
        bucket_name=bucket,
        object_path=object_path,
        data=raw,
        overwrite=overwrite,
        metadata=obj_metadata,
    )

    logger.info(
        "ingest_market_share_complete",
        snapshot_date=resolved_date.isoformat(),
        snapshot_at=snapshot_at.isoformat(),
        dex_count=dex_count,
        gcs_uri=gcs_uri,
    )

    return {
        "gcs_uri": gcs_uri,
        "snapshot_at": snapshot_at.isoformat(),
        "snapshot_date": resolved_date.isoformat(),
        "dex_count": dex_count,
    }
