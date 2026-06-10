import json
from datetime import date
from typing import Any

from google.cloud import storage  # type: ignore[import-untyped,attr-defined]

from src.utils.logging import get_logger
from src.utils.temporal import date_to_compact

logger = get_logger(__name__)


def build_pool_partition_path(dex: str, snapshot_date: date) -> str:
    # produces: raw/dex_pools/dex=raydium/date=2026-06-03/raydium_20260603.json
    iso = snapshot_date.isoformat()
    compact = date_to_compact(snapshot_date)
    return f"raw/dex_pools/dex={dex}/date={iso}/{dex}_{compact}.json"


def build_market_share_partition_path(snapshot_date: date) -> str:
    # produces: raw/dex_market_share/date=2026-06-03/defillama_20260603.json
    iso = snapshot_date.isoformat()
    compact = date_to_compact(snapshot_date)
    return f"raw/dex_market_share/date={iso}/defillama_{compact}.json"


def check_object_exists(bucket_name: str, object_path: str) -> bool:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    return bool(blob.exists())


def write_json_to_gcs(
    bucket_name: str,
    object_path: str,
    data: dict[str, Any],
    overwrite: bool = False,
    metadata: dict[str, str] | None = None,
) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    if not overwrite and blob.exists():
        raise FileExistsError(f"gs://{bucket_name}/{object_path} already exists")

    # metadata is stored as GCS object attributes, not inside the JSON itself
    if metadata:
        blob.metadata = metadata

    content = json.dumps(data, default=str).encode("utf-8")
    blob.upload_from_string(content, content_type="application/json", timeout=600)

    uri = f"gs://{bucket_name}/{object_path}"
    logger.info("gcs_write_complete", uri=uri, bytes_written=len(content))
    return uri


def get_object_metadata(bucket_name: str, object_path: str) -> dict[str, str]:
    # fetches the latest blob state from GCS including its metadata fields
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    blob.reload()
    return dict(blob.metadata or {})


def read_json_from_gcs(uri: str) -> dict[str, Any]:
    # parse gs://bucket/path/to/file.json into its components
    without_scheme = uri.removeprefix("gs://")
    bucket_name, _, object_path = without_scheme.partition("/")
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(object_path)
    return dict(json.loads(blob.download_as_text()))
