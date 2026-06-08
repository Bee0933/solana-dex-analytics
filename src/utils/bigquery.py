from datetime import date
from typing import Any

from google.cloud import bigquery  # type: ignore[import-untyped]

from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_bq_client(project_id: str | None = None) -> bigquery.Client:
    # uses Application Default Credentials — no key file needed in Cloud Run
    return bigquery.Client(project=project_id or None)


def get_pools_schema() -> list[bigquery.SchemaField]:
    # mirrors the unified raw_dex_pools schema from the pre-flight spec
    return [
        bigquery.SchemaField("snapshot_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("dex_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("pool_address", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("base_token_symbol", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("base_token_address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("quote_token_symbol", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("quote_token_address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("trailing_24h_volume_usd", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("trailing_24h_fees_usd", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("tvl_usd", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("source_file", "STRING", mode="REQUIRED"),
    ]


def get_market_share_schema() -> list[bigquery.SchemaField]:
    # mirrors the raw_dex_market_share schema from the pre-flight spec
    return [
        bigquery.SchemaField("snapshot_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("dex_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("trailing_24h_volume_usd", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("trailing_7d_volume_usd", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("total_volume_usd", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("source_file", "STRING", mode="REQUIRED"),
    ]


def create_pools_table_if_not_exists(
    client: bigquery.Client,
    dataset_id: str,
    table_id: str = "raw_dex_pools",
) -> bigquery.Table:
    ref = f"{client.project}.{dataset_id}.{table_id}"
    table = bigquery.Table(ref, schema=get_pools_schema())
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="snapshot_date",  # BQ only scans the relevant day partition on queries
    )
    table.clustering_fields = ["dex_name", "pool_address"]
    return client.create_table(table, exists_ok=True)  # safe to call on every run


def create_market_share_table_if_not_exists(
    client: bigquery.Client,
    dataset_id: str,
    table_id: str = "raw_dex_market_share",
) -> bigquery.Table:
    ref = f"{client.project}.{dataset_id}.{table_id}"
    table = bigquery.Table(ref, schema=get_market_share_schema())
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="snapshot_date",
    )
    table.clustering_fields = ["dex_name"]
    return client.create_table(table, exists_ok=True)


def rows_exist_for_snapshot(
    client: bigquery.Client,
    dataset_id: str,
    table_id: str,
    snapshot_date: date,
    dex_name: str | None = None,
) -> bool:
    # used before loading to decide whether to skip or delete first
    table_ref = f"`{client.project}.{dataset_id}.{table_id}`"
    query = f"SELECT COUNT(1) AS cnt FROM {table_ref} WHERE snapshot_date = @snapshot_date"
    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("snapshot_date", "DATE", snapshot_date.isoformat()),
    ]
    if dex_name:
        query += " AND dex_name = @dex_name"
        params.append(bigquery.ScalarQueryParameter("dex_name", "STRING", dex_name))
    result = client.query(
        query, job_config=bigquery.QueryJobConfig(query_parameters=params)
    ).result()
    row = next(iter(result))
    return int(row.cnt) > 0


def delete_snapshot(
    client: bigquery.Client,
    dataset_id: str,
    table_id: str,
    snapshot_date: date,
    dex_name: str | None = None,
) -> int:
    # only called when overwrite=True — clears the slice so we can reload cleanly
    table_ref = f"`{client.project}.{dataset_id}.{table_id}`"
    query = f"DELETE FROM {table_ref} WHERE snapshot_date = @snapshot_date"
    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("snapshot_date", "DATE", snapshot_date.isoformat()),
    ]
    if dex_name:
        query += " AND dex_name = @dex_name"
        params.append(bigquery.ScalarQueryParameter("dex_name", "STRING", dex_name))
    job = client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params))
    job.result()
    return int(job.num_dml_affected_rows or 0)


def load_rows(
    client: bigquery.Client,
    table_ref: str,
    rows: list[dict[str, Any]],
    schema: list[bigquery.SchemaField],
) -> tuple[int, str]:
    # WRITE_APPEND adds to the table, does not overwrites the whole thing
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()  # blocks until the load job finishes
    if job.errors:
        raise RuntimeError(f"BQ load job failed: {job.errors}")
    return int(job.output_rows or 0), job.job_id
