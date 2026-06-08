from datetime import date, datetime, timezone

import pytest

from src.sources.orca.parser import OrcaParser, _to_float

_SNAPSHOT_AT = datetime(2026, 6, 2, 2, 0, 0, tzinfo=timezone.utc)
_SNAPSHOT_DATE = date(2026, 6, 1)
_SOURCE_FILE = "gs://bucket/raw/dex_pools/dex=orca/date=2026-06-01/data.json"

_FULL_POOL = {
    "address": "orca_pool_abc",
    "tokenA": {
        "symbol": "SOL",
        "address": "So1111111111111111111111111111111111111111",
    },
    "tokenB": {
        "symbol": "USDC",
        "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    },
    "tvlUsdc": "26153679.3112215291676728684249531120",
    "stats": {
        "24h": {
            "volume": "122201862.92057900",
            "fees": "48878.05032843170542979000",
        }
    },
}


@pytest.fixture()
def parser() -> OrcaParser:
    return OrcaParser()


# --- _to_float helper ---

def test_to_float_converts_string() -> None:
    assert _to_float("122201862.92") == pytest.approx(122_201_862.92)


def test_to_float_handles_none() -> None:
    assert _to_float(None) is None


def test_to_float_handles_number() -> None:
    assert _to_float(3.14) == pytest.approx(3.14)


def test_to_float_handles_invalid_string() -> None:
    assert _to_float("not_a_number") is None


# --- parser ---

def test_parse_maps_all_fields(parser: OrcaParser) -> None:
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["dex_name"] == "orca"
    assert row["pool_address"] == "orca_pool_abc"
    assert row["base_token_symbol"] == "SOL"
    assert row["base_token_address"] == "So1111111111111111111111111111111111111111"
    assert row["quote_token_symbol"] == "USDC"
    assert row["trailing_24h_volume_usd"] == pytest.approx(122_201_862.92057900)
    assert row["trailing_24h_fees_usd"] == pytest.approx(48_878.05032843, rel=1e-5)
    assert row["tvl_usd"] == pytest.approx(26_153_679.31, rel=1e-5)
    assert row["source_file"] == _SOURCE_FILE


def test_parse_stamps_snapshot_columns(parser: OrcaParser) -> None:
    rows = parser.parse(
        {"pools": [_FULL_POOL]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows[0]["snapshot_at"] == _SNAPSHOT_AT
    assert rows[0]["snapshot_date"] == _SNAPSHOT_DATE


def test_parse_skips_pool_missing_address(parser: OrcaParser) -> None:
    pool_no_addr = {k: v for k, v in _FULL_POOL.items() if k != "address"}
    rows = parser.parse(
        {"pools": [pool_no_addr]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows == []


def test_parse_handles_null_stats(parser: OrcaParser) -> None:
    minimal = {
        "address": "pool_xyz",
        "tokenA": None,
        "tokenB": None,
        "tvlUsdc": None,
        "stats": None,
    }
    rows = parser.parse(
        {"pools": [minimal]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["trailing_24h_volume_usd"] is None
    assert row["trailing_24h_fees_usd"] is None
    assert row["tvl_usd"] is None


def test_parse_output_has_all_schema_keys(parser: OrcaParser) -> None:
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
