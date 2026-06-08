import httpx
import pytest
import respx

from src.sources.orca.client import OrcaClient

_POOL = {
    "address": "orca_pool_1",
    "tokenA": {"symbol": "SOL", "address": "So1111"},
    "tokenB": {"symbol": "USDC", "address": "EPjFWdd"},
    "tvlUsdc": "1000000.00",
    "stats": {"24h": {"volume": "50000.00", "fees": "25.00"}},
}

_SINGLE_PAGE = {
    "data": [_POOL],
    "meta": {"cursor": {"previous": None, "next": None}},
}

_PAGE_1 = {
    "data": [_POOL],
    "meta": {"cursor": {"previous": None, "next": "cursor_abc"}},
}
_PAGE_2 = {
    "data": [{**_POOL, "address": "orca_pool_2"}],
    "meta": {"cursor": {"previous": "cursor_abc", "next": None}},
}


@respx.mock
def test_fetch_single_page_returns_pools() -> None:
    # No next cursor returned — client should return the one pool and stop.
    respx.get("https://api.orca.so/v2/solana/pools").mock(
        return_value=httpx.Response(200, json=_SINGLE_PAGE)
    )
    client = OrcaClient()
    result = client.fetch()
    assert len(result["pools"]) == 1
    assert result["pools"][0]["address"] == "orca_pool_1"


@respx.mock
def test_fetch_cursor_pagination() -> None:
    # First page has a next cursor — client should follow it and merge both pages.
    route = respx.get("https://api.orca.so/v2/solana/pools")
    route.side_effect = [
        httpx.Response(200, json=_PAGE_1),
        httpx.Response(200, json=_PAGE_2),
    ]
    client = OrcaClient()
    result = client.fetch()
    assert len(result["pools"]) == 2
    assert route.call_count == 2


@respx.mock
def test_fetch_stops_at_max_pages() -> None:
    # Cursor keeps coming back — client should stop after max_pages=1.
    respx.get("https://api.orca.so/v2/solana/pools").mock(
        return_value=httpx.Response(200, json=_PAGE_1)
    )
    client = OrcaClient(max_pages=1)
    result = client.fetch()
    assert len(result["pools"]) == 1


@respx.mock
def test_fetch_retries_on_500() -> None:
    # Server errors once then succeeds — client should retry and return the data.
    route = respx.get("https://api.orca.so/v2/solana/pools")
    route.side_effect = [
        httpx.Response(500, json={"error": "server error"}),
        httpx.Response(200, json=_SINGLE_PAGE),
    ]
    client = OrcaClient()
    result = client.fetch()
    assert len(result["pools"]) == 1
    assert route.call_count == 2


@respx.mock
def test_fetch_retries_on_429() -> None:
    # Rate limited on first call — client should retry and succeed on second.
    route = respx.get("https://api.orca.so/v2/solana/pools")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, json=_SINGLE_PAGE),
    ]
    client = OrcaClient()
    result = client.fetch()
    assert route.call_count == 2
