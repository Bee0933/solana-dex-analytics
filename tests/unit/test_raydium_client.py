import httpx
import pytest
import respx

from src.sources.raydium.client import RaydiumClient

_SINGLE_PAGE = {
    "success": True,
    "data": {
        "count": 1,
        "hasNextPage": False,
        "data": [
            {
                "id": "pool_abc123",
                "mintA": {"symbol": "SOL", "address": "So1111111111111111111111111111111111111111"},
                "mintB": {"symbol": "USDC", "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"},
                "tvl": 1_500_000.0,
                "day": {"volume": 75_000.0, "volumeFee": 7.5},
            }
        ],
    },
}

_TWO_PAGES = {
    "page1": {
        "success": True,
        "data": {
            "count": 2,
            "hasNextPage": True,
            "data": [{"id": "p1", "mintA": {}, "mintB": {}, "tvl": 1.0, "day": {}}],
        },
    },
    "page2": {
        "success": True,
        "data": {
            "count": 2,
            "hasNextPage": False,
            "data": [{"id": "p2", "mintA": {}, "mintB": {}, "tvl": 2.0, "day": {}}],
        },
    },
}


@respx.mock
def test_fetch_single_page_returns_pools() -> None:
    # API returns one page — client should give back that one pool.
    respx.get("https://api-v3.raydium.io/pools/info/list").mock(
        return_value=httpx.Response(200, json=_SINGLE_PAGE)
    )
    client = RaydiumClient()
    result = client.fetch()
    assert isinstance(result["pools"], list)
    assert len(result["pools"]) == 1
    assert result["pools"][0]["id"] == "pool_abc123"


@respx.mock
def test_fetch_paginates_multiple_pages() -> None:
    # First page says there's more data; client should fetch page 2 and merge both.
    route = respx.get("https://api-v3.raydium.io/pools/info/list")
    route.side_effect = [
        httpx.Response(200, json=_TWO_PAGES["page1"]),
        httpx.Response(200, json=_TWO_PAGES["page2"]),
    ]
    client = RaydiumClient()
    result = client.fetch()
    assert len(result["pools"]) == 2
    assert route.call_count == 2


@respx.mock
def test_fetch_stops_at_max_pages() -> None:
    # API keeps saying there are more pages — client should stop at max_pages=1.
    respx.get("https://api-v3.raydium.io/pools/info/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"count": 99, "hasNextPage": True, "data": [{"id": "p1"}]},
            },
        )
    )
    client = RaydiumClient(max_pages=1)
    result = client.fetch()
    assert len(result["pools"]) == 1


@respx.mock
def test_fetch_retries_on_500() -> None:
    # Server errors once then succeeds — client should retry and return the data.
    route = respx.get("https://api-v3.raydium.io/pools/info/list")
    route.side_effect = [
        httpx.Response(500, json={"error": "server error"}),
        httpx.Response(200, json=_SINGLE_PAGE),
    ]
    client = RaydiumClient()
    result = client.fetch()
    assert len(result["pools"]) == 1
    assert route.call_count == 2


@respx.mock
def test_fetch_retries_on_429() -> None:
    # Rate limited on first call — client should retry and succeed on second.
    route = respx.get("https://api-v3.raydium.io/pools/info/list")
    route.side_effect = [
        httpx.Response(429, json={"error": "rate limited"}),
        httpx.Response(200, json=_SINGLE_PAGE),
    ]
    client = RaydiumClient()
    result = client.fetch()
    assert route.call_count == 2
