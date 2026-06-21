import json
from datetime import date
from typing import Any

from google.cloud import storage  # type: ignore[import-untyped,attr-defined]

from src.config import settings
from src.logging import get_logger

logger = get_logger(__name__)


def _client() -> storage.Client:
    # pass the project explicitly so it works with user ADC locally (Cloud Run can
    # auto-detect it, but a local login can't)
    return storage.Client(project=settings.gcp_project_id or None)


def _compact(d: date) -> str:
    return d.strftime("%Y%m%d")


def build_pool_partition_path(dex: str, snapshot_date: date) -> str:
    # produces: raw/dex_pools/dex=raydium/date=2026-06-03/raydium_20260603.json
    iso = snapshot_date.isoformat()
    return f"raw/dex_pools/dex={dex}/date={iso}/{dex}_{_compact(snapshot_date)}.json"


def build_market_share_partition_path(snapshot_date: date) -> str:
    # produces: raw/dex_market_share/date=2026-06-03/defillama_20260603.json
    iso = snapshot_date.isoformat()
    return f"raw/dex_market_share/date={iso}/defillama_{_compact(snapshot_date)}.json"


def check_object_exists(bucket_name: str, object_path: str) -> bool:
    client = _client()
    return bool(client.bucket(bucket_name).blob(object_path).exists())


def write_json_to_gcs(
    bucket_name: str,
    object_path: str,
    data: dict[str, Any],
    overwrite: bool = False,
    metadata: dict[str, str] | None = None,
) -> str:
    client = _client()
    blob = client.bucket(bucket_name).blob(object_path)

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
    client = _client()
    blob = client.bucket(bucket_name).blob(object_path)
    blob.reload()
    return dict(blob.metadata or {})


def read_json_from_gcs(uri: str) -> dict[str, Any]:
    # parse gs://bucket/path/to/file.json into its components
    without_scheme = uri.removeprefix("gs://")
    bucket_name, _, object_path = without_scheme.partition("/")
    client = _client()
    blob = client.bucket(bucket_name).blob(object_path)
    return dict(json.loads(blob.download_as_text()))
