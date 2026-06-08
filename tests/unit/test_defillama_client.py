import httpx
import pytest
import respx

from src.sources.defillama.client import DefiLlamaClient

_RESPONSE = {
    "total24h": 1_789_993_651,
    "total7d": 9_462_209_560,
    "protocols": [
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
    ],
}


@respx.mock
def test_fetch_returns_protocols() -> None:
    # Normal successful response — client should return the protocols list as-is.
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json=_RESPONSE)
    )
    client = DefiLlamaClient()
    result = client.fetch()
    assert "protocols" in result
    assert isinstance(result["protocols"], list)
    assert len(result["protocols"]) == 2


@respx.mock
def test_fetch_passes_exclude_params() -> None:
    # Check the client sends the right query params to keep the response small.
    route = respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json=_RESPONSE)
    )
    client = DefiLlamaClient()
    client.fetch()
    assert route.called
    request = route.calls.last.request
    assert "excludeTotalDataChart=true" in str(request.url)


@respx.mock
def test_fetch_retries_on_500() -> None:
    # Server errors once then succeeds — client should retry and return the data.
    route = respx.get("https://api.llama.fi/overview/dexs/solana")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json=_RESPONSE),
    ]
    client = DefiLlamaClient()
    result = client.fetch()
    assert "protocols" in result
    assert route.call_count == 2


@respx.mock
def test_fetch_retries_on_429() -> None:
    # Rate limited on first call — client should retry and succeed on second.
    route = respx.get("https://api.llama.fi/overview/dexs/solana")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, json=_RESPONSE),
    ]
    client = DefiLlamaClient()
    client.fetch()
    assert route.call_count == 2
