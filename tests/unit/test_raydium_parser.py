from datetime import date, datetime, timezone

import pytest

from src.sources.raydium.parser import RaydiumParser

_SNAPSHOT_AT = datetime(2026, 6, 2, 2, 0, 0, tzinfo=timezone.utc)
_SNAPSHOT_DATE = date(2026, 6, 1)
_SOURCE_FILE = "gs://bucket/raw/dex_pools/dex=raydium/date=2026-06-01/data.json"

_FULL_POOL = {
    "id": "pool_abc123",
    "mintA": {
        "symbol": "SOL",
        "address": "So1111111111111111111111111111111111111111",
    },
    "mintB": {
        "symbol": "USDC",
        "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    },
    "tvl": 1_500_000.0,
    "day": {"volume": 75_000.0, "volumeFee": 7.5},
}


@pytest.fixture()
def parser() -> RaydiumParser:
    return RaydiumParser()


def test_parse_maps_all_fields(parser: RaydiumParser) -> None:
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["dex_name"] == "raydium"
    assert row["pool_address"] == "pool_abc123"
    assert row["base_token_symbol"] == "SOL"
    assert row["base_token_address"] == "So1111111111111111111111111111111111111111"
    assert row["quote_token_symbol"] == "USDC"
    assert row["quote_token_address"] == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    assert row["trailing_24h_volume_usd"] == 75_000.0
    assert row["trailing_24h_fees_usd"] == 7.5
    assert row["tvl_usd"] == 1_500_000.0
    assert row["source_file"] == _SOURCE_FILE


def test_parse_stamps_snapshot_columns(parser: RaydiumParser) -> None:
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows[0]["snapshot_at"] == _SNAPSHOT_AT
    assert rows[0]["snapshot_date"] == _SNAPSHOT_DATE


def test_parse_skips_pool_missing_id(parser: RaydiumParser) -> None:
    pool_no_id = {k: v for k, v in _FULL_POOL.items() if k != "id"}
    rows = parser.parse(
        {"pools": [pool_no_id]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows == []


def test_parse_handles_null_optional_fields(parser: RaydiumParser) -> None:
    minimal = {"id": "pool_xyz", "mintA": None, "mintB": None, "tvl": None, "day": None}
    rows = parser.parse(
        {"pools": [minimal]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["pool_address"] == "pool_xyz"
    assert row["base_token_symbol"] is None
    assert row["trailing_24h_volume_usd"] is None
    assert row["tvl_usd"] is None


def test_parse_empty_response(parser: RaydiumParser) -> None:
    assert parser.parse({"pools": []}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE) == []


def test_parse_multiple_pools(parser: RaydiumParser) -> None:
    pool2 = {**_FULL_POOL, "id": "pool_def456"}
    rows = parser.parse(
        {"pools": [_FULL_POOL, pool2]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 2
    assert {r["pool_address"] for r in rows} == {"pool_abc123", "pool_def456"}


def test_parse_output_has_all_schema_keys(parser: RaydiumParser) -> None:
    expected_keys = {
        "snapshot_at",
        "snapshot_date",
        "dex_name",
        "pool_address",
        "base_token_symbol",
        "base_token_address",
        "quote_token_symbol",
        "quote_token_address",
        "trailing_24h_volume_usd",
        "trailing_24h_fees_usd",
        "tvl_usd",
        "source_file",
    }
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert set(rows[0].keys()) == expected_keys
