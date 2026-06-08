from datetime import date, datetime, timezone

import pytest

from src.sources.defillama.parser import DefiLlamaParser, _is_included

_SNAPSHOT_AT = datetime(2026, 6, 2, 2, 0, 0, tzinfo=timezone.utc)
_SNAPSHOT_DATE = date(2026, 6, 1)
_SOURCE_FILE = "gs://bucket/raw/dex_market_share/date=2026-06-01/data.json"

_PROTOCOLS = [
    {
        "name": "Raydium AMM",
        "total24h": 169_316_785,
        "total7d": 978_695_846,
        "totalAllTime": 706_847_906_618,
    },
    {
        "name": "Orca DEX",
        "total24h": 220_137_866,
        "total7d": 1_217_394_681,
        "totalAllTime": 473_111_779_551,
    },
    {
        "name": "Meteora DLMM",
        "total24h": 163_093_174,
        "total7d": 809_777_365,
        "totalAllTime": 205_738_755_652,
    },
    {
        "name": "Serum",
        "total24h": None,
        "total7d": None,
        "totalAllTime": 3_488_914_577,
    },
]


@pytest.fixture()
def parser() -> DefiLlamaParser:
    return DefiLlamaParser()


# _is_included helper functions
def test_is_included_raydium() -> None:
    assert _is_included("Raydium AMM") is True

def test_is_included_orca() -> None:
    assert _is_included("Orca DEX") is True

def test_is_included_meteora_variants() -> None:
    for name in ["Meteora DLMM", "Meteora DAMM V1", "Meteora DAMM V2"]:
        assert _is_included(name) is True

def test_is_included_excludes_serum() -> None:
    assert _is_included("Serum") is False


# parser
def test_parse_filters_to_target_protocols(parser: DefiLlamaParser) -> None:
    rows = parser.parse(
        {"protocols": _PROTOCOLS}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    names = {r["dex_name"] for r in rows}
    assert "serum" not in names
    assert len(rows) == 3  # raydium, orca, meteora


def test_parse_maps_all_fields(parser: DefiLlamaParser) -> None:
    rows = parser.parse(
        {"protocols": [_PROTOCOLS[0]]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["dex_name"] == "raydium amm"
    assert row["trailing_24h_volume_usd"] == 169_316_785
    assert row["trailing_7d_volume_usd"] == 978_695_846
    assert row["total_volume_usd"] == 706_847_906_618
    assert row["source_file"] == _SOURCE_FILE


def test_parse_stamps_snapshot_columns(parser: DefiLlamaParser) -> None:
    rows = parser.parse(
        {"protocols": [_PROTOCOLS[0]]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows[0]["snapshot_at"] == _SNAPSHOT_AT
    assert rows[0]["snapshot_date"] == _SNAPSHOT_DATE


def test_parse_handles_null_24h_volume(parser: DefiLlamaParser) -> None:
    proto_null = {
        "name": "Meteora DAMM V1",
        "total24h": None,
        "total7d": 9_536_639,
        "totalAllTime": 28_825_282_896,
    }
    rows = parser.parse(
        {"protocols": [proto_null]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert len(rows) == 1
    assert rows[0]["trailing_24h_volume_usd"] is None
    assert rows[0]["trailing_7d_volume_usd"] == 9_536_639


def test_parse_empty_protocols(parser: DefiLlamaParser) -> None:
    rows = parser.parse(
        {"protocols": []}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert rows == []


def test_parse_output_has_market_share_schema_keys(parser: DefiLlamaParser) -> None:
    expected_keys = {
        "snapshot_at",
        "snapshot_date",
        "dex_name",
        "trailing_24h_volume_usd",
        "trailing_7d_volume_usd",
        "total_volume_usd",
        "source_file",
    }
    rows = parser.parse(
        {"protocols": [_PROTOCOLS[0]]}, _SNAPSHOT_AT, _SNAPSHOT_DATE, _SOURCE_FILE
    )
    assert set(rows[0].keys()) == expected_keys
