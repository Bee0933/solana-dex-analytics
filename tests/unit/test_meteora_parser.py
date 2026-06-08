from datetime import date, datetime, timezone

import pytest

from src.sources.meteora.parser import MeteoraParser, _parse_symbols

_SNAPSHOT_AT = datetime(2026, 6, 2, 2, 0, 0, tzinfo=timezone.utc)
_SNAPSHOT_DATE = date(2026, 6, 1)
_SOURCE_FILE = "gs://bucket/raw/dex_pools/dex=meteora/date=2026-06-01/data.json"

_FULL_POOL = {
    "pool_address": "meteora_pool_abc",
    "pool_name": "SOL-JitoSOL",
    "pool_token_mints": [
        "So1111111111111111111111111111111111111111",
        "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
    ],
    "pool_tvl": 2_094_752.0,
    "trading_volume": 769_899.9,
    "fee_volume": 77.0,
}


@pytest.fixture()
def parser() -> MeteoraParser:
    return MeteoraParser()


# --- _parse_symbols helper ---

def test_parse_symbols_standard() -> None:
    assert _parse_symbols("SOL-USDC") == ("SOL", "USDC")


def test_parse_symbols_jitoSOL() -> None:
    assert _parse_symbols("SOL-JitoSOL") == ("SOL", "JitoSOL")


def test_parse_symbols_no_dash() -> None:
    assert _parse_symbols("SOLANA") == (None, None)


def test_parse_symbols_none() -> None:
    assert _parse_symbols(None) == (None, None)


def test_parse_symbols_empty_string() -> None:
    assert _parse_symbols("") == (None, None)


# --- parser ---

def test_parse_maps_all_fields(parser: MeteoraParser) -> None:
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["dex_name"] == "meteora"
    assert row["pool_address"] == "meteora_pool_abc"
    assert row["base_token_symbol"] == "SOL"
    assert row["base_token_address"] == "So1111111111111111111111111111111111111111"
    assert row["quote_token_symbol"] == "JitoSOL"
    assert row["quote_token_address"] == "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"
    assert row["trailing_24h_volume_usd"] == pytest.approx(769_899.9)
    assert row["trailing_24h_fees_usd"] == pytest.approx(77.0)
    assert row["tvl_usd"] == pytest.approx(2_094_752.0)
    assert row["source_file"] == _SOURCE_FILE


def test_parse_stamps_snapshot_columns(parser: MeteoraParser) -> None:
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows[0]["snapshot_at"] == _SNAPSHOT_AT
    assert rows[0]["snapshot_date"] == _SNAPSHOT_DATE


def test_parse_skips_pool_missing_address(parser: MeteoraParser) -> None:
    pool_no_addr = {k: v for k, v in _FULL_POOL.items() if k != "pool_address"}
    rows = parser.parse(
        {"pools": [pool_no_addr]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows == []


def test_parse_handles_missing_mints(parser: MeteoraParser) -> None:
    minimal = {**_FULL_POOL, "pool_token_mints": [], "pool_name": None}
    rows = parser.parse(
        {"pools": [minimal]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    assert rows[0]["base_token_address"] is None
    assert rows[0]["quote_token_address"] is None
    assert rows[0]["base_token_symbol"] is None


def test_parse_handles_null_volumes(parser: MeteoraParser) -> None:
    pool = {**_FULL_POOL, "trading_volume": None, "fee_volume": None, "pool_tvl": None}
    rows = parser.parse(
        {"pools": [pool]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows[0]["trailing_24h_volume_usd"] is None
    assert rows[0]["trailing_24h_fees_usd"] is None
    assert rows[0]["tvl_usd"] is None


def test_parse_output_has_all_schema_keys(parser: MeteoraParser) -> None:
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
