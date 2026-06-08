"""Live integration tests — hit the real APIs once and assert basic shape.
"""

import pytest

from src.sources.defillama.client import DefiLlamaClient
from src.sources.meteora.client import MeteoraClient
from src.sources.orca.client import OrcaClient
from src.sources.raydium.client import RaydiumClient


@pytest.mark.integration
def test_raydium_live_fetch() -> None:
    client = RaydiumClient(max_pages=1)
    result = client.fetch()
    assert "pools" in result
    pools = result["pools"]
    assert len(pools) > 0
    pool = pools[0]
    assert "id" in pool
    assert "mintA" in pool
    assert "mintB" in pool
    assert "tvl" in pool
    assert "day" in pool


@pytest.mark.integration
def test_orca_live_fetch() -> None:
    client = OrcaClient(max_pages=1)
    result = client.fetch()
    assert "pools" in result
    pools = result["pools"]
    assert len(pools) > 0
    pool = pools[0]
    assert "address" in pool
    assert "tokenA" in pool
    assert "tokenB" in pool
    assert "tvlUsdc" in pool
    assert "stats" in pool
    assert "24h" in pool["stats"]


@pytest.mark.integration
def test_meteora_live_fetch() -> None:
    client = MeteoraClient(max_pages=1)
    result = client.fetch()
    assert "pools" in result
    pools = result["pools"]
    assert len(pools) > 0
    pool = pools[0]
    assert "pool_address" in pool
    assert "pool_token_mints" in pool
    assert "trading_volume" in pool
    assert "pool_tvl" in pool


@pytest.mark.integration
def test_defillama_live_fetch() -> None:
    client = DefiLlamaClient()
    result = client.fetch()
    assert "protocols" in result
    protocols = result["protocols"]
    assert len(protocols) > 0
    names = {p.get("name", "").lower() for p in protocols}
    assert any("raydium" in n for n in names)
    assert any("orca" in n for n in names)
    assert any("meteora" in n for n in names)


@pytest.mark.integration
def test_raydium_live_parser_schema() -> None:
    from datetime import date, datetime, timezone

    from src.sources.raydium.parser import RaydiumParser

    snapshot_at = datetime.now(timezone.utc)
    snapshot_date = date.today()
    client = RaydiumClient(max_pages=1)
    parser = RaydiumParser()
    response = client.fetch()
    rows = parser.parse(response, snapshot_at, snapshot_date, "gs://test/file.json")
    assert len(rows) > 0
    required = {
        "snapshot_at",
        "snapshot_date",
        "dex_name",
        "pool_address",
        "trailing_24h_volume_usd",
        "source_file",
    }
    assert required.issubset(rows[0].keys())


@pytest.mark.integration
def test_orca_live_parser_schema() -> None:
    from datetime import date, datetime, timezone

    from src.sources.orca.parser import OrcaParser

    snapshot_at = datetime.now(timezone.utc)
    snapshot_date = date.today()
    client = OrcaClient(max_pages=1)
    parser = OrcaParser()
    response = client.fetch()
    rows = parser.parse(response, snapshot_at, snapshot_date, "gs://test/file.json")
    assert len(rows) > 0
    required = {
        "snapshot_at",
        "snapshot_date",
        "dex_name",
        "pool_address",
        "trailing_24h_volume_usd",
        "source_file",
    }
    assert required.issubset(rows[0].keys())


@pytest.mark.integration
def test_meteora_live_parser_schema() -> None:
    from datetime import date, datetime, timezone

    from src.sources.meteora.parser import MeteoraParser

    snapshot_at = datetime.now(timezone.utc)
    snapshot_date = date.today()
    client = MeteoraClient(max_pages=1)
    parser = MeteoraParser()
    response = client.fetch()
    rows = parser.parse(response, snapshot_at, snapshot_date, "gs://test/file.json")
    assert len(rows) > 0
    required = {
        "snapshot_at",
        "snapshot_date",
        "dex_name",
        "pool_address",
        "trailing_24h_volume_usd",
        "source_file",
    }
    assert required.issubset(rows[0].keys())


@pytest.mark.integration
def test_defillama_live_parser_schema() -> None:
    from datetime import date, datetime, timezone

    from src.sources.defillama.parser import DefiLlamaParser

    snapshot_at = datetime.now(timezone.utc)
    snapshot_date = date.today()
    client = DefiLlamaClient()
    parser = DefiLlamaParser()
    response = client.fetch()
    rows = parser.parse(response, snapshot_at, snapshot_date, "gs://test/file.json")
    assert len(rows) > 0
    required = {
        "snapshot_at",
        "snapshot_date",
        "dex_name",
        "trailing_24h_volume_usd",
        "source_file",
    }
    assert required.issubset(rows[0].keys())
