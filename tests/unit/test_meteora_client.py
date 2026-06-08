import httpx
import pytest
import respx

from src.sources.meteora.client import MeteoraClient

_POOL = {
    "pool_address": "meteora_pool_1",
    "pool_name": "SOL-USDC",
    "pool_token_mints": ["So1111", "EPjFWdd"],
    "pool_tvl": 2_000_000.0,
    "trading_volume": 800_000.0,
    "fee_volume": 800.0,
}

_SINGLE_PAGE = {"data": [_POOL], "page": 0, "total_count": 1}
_PAGE_1 = {"data": [_POOL], "page": 0, "total_count": 2}
_PAGE_2 = {"data": [{**_POOL, "pool_address": "meteora_pool_2"}], "page": 1, "total_count": 2}


@respx.mock
def test_fetch_single_page_returns_pools() -> None:
    # Total count matches one page — client should return that pool and stop.
    respx.get("https://amm-v2.meteora.ag/pools/search").mock(
        return_value=httpx.Response(200, json=_SINGLE_PAGE)
    )
    client = MeteoraClient()
    result = client.fetch()
    assert len(result["pools"]) == 1
    assert result["pools"][0]["pool_address"] == "meteora_pool_1"


@respx.mock
def test_fetch_paginates_multiple_pages() -> None:
    # Total count is 2 but page 1 only has 1 pool — client should fetch page 2 and merge.
    route = respx.get("https://amm-v2.meteora.ag/pools/search")
    route.side_effect = [
        httpx.Response(200, json=_PAGE_1),
        httpx.Response(200, json=_PAGE_2),
    ]
    client = MeteoraClient()
    result = client.fetch()
    assert len(result["pools"]) == 2
    assert route.call_count == 2


@respx.mock
def test_fetch_stops_at_max_pages() -> None:
    # Total count is huge but max_pages=1 — client should stop after first page.
    respx.get("https://amm-v2.meteora.ag/pools/search").mock(
        return_value=httpx.Response(
            200, json={"data": [_POOL], "page": 0, "total_count": 100_000}
        )
    )
    client = MeteoraClient(max_pages=1)
    result = client.fetch()
    assert len(result["pools"]) == 1


@respx.mock
def test_fetch_retries_on_500() -> None:
    # Server errors once then succeeds — client should retry and return the data.
    route = respx.get("https://amm-v2.meteora.ag/pools/search")
    route.side_effect = [
        httpx.Response(500, json={"error": "server error"}),
        httpx.Response(200, json=_SINGLE_PAGE),
    ]
    client = MeteoraClient()
    result = client.fetch()
    assert len(result["pools"]) == 1
    assert route.call_count == 2


@respx.mock
def test_fetch_retries_on_429() -> None:
    # Rate limited on first call — client should retry and succeed on second.
    route = respx.get("https://amm-v2.meteora.ag/pools/search")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, json=_SINGLE_PAGE),
    ]
    client = MeteoraClient()
    result = client.fetch()
    assert route.call_count == 2
