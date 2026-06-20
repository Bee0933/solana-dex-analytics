"""Data sources: one fetch() + parse() pair per DEX, plus a shared HTTP helper.

fetch_* functions pull raw JSON from each API (with retries on transient errors).
parse_* functions map that raw JSON onto our unified BigQuery schemas.
"""

import time
from datetime import date, datetime
from typing import Any, cast

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = 30
_MAX_PAGES = 50


def _is_retryable(exc: BaseException) -> bool:
    # retry on server errors and rate limits, not on bad requests (404, 403 etc.)
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, httpx.TransportError)


@retry(
    stop=stop_after_attempt(3),  # try at most 3 times
    wait=wait_exponential(multiplier=1, min=2, max=30),  # wait 2s, 4s, up to 30s
    retry=retry_if_exception(_is_retryable),  # only retry errors worth retrying
    reraise=True,  # if all 3 fail, raise the original error
)
def get_json(
    client: httpx.Client, url: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    t0 = time.monotonic()
    response = client.get(url, params=params)
    latency_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "http_get",
        url=url,
        status_code=response.status_code,
        latency_ms=round(latency_ms, 1),
        response_bytes=len(response.content),
    )
    response.raise_for_status()  # non-2xx triggers the retry logic above
    return cast(dict[str, Any], response.json())


def _to_float(val: Any) -> float | None:
    # Orca returns stats/TVL as high-precision decimal strings, not JSON numbers.
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# Quality floors: keep only pools with real liquidity AND real activity. This drops
# wash-traded spam (high volume on ~$0 TVL) and dead pools (no volume). Easy to tune.
_VOLUME_FLOOR = 1000.0  # USD, trailing 24h
_TVL_FLOOR = 1000.0  # USD


def _keep(volume: Any, tvl: Any) -> bool:
    # coerce first — some APIs return these as strings (e.g. Meteora's pool_tvl)
    return (_to_float(volume) or 0) >= _VOLUME_FLOOR and (_to_float(tvl) or 0) >= _TVL_FLOOR


# Raydium — https://api-v3.raydium.io
_RAYDIUM_URL = "https://api-v3.raydium.io"


def fetch_raydium() -> dict[str, Any]:
    """Page through Raydium pools (sorted by 24h volume desc) down to the volume floor."""
    all_pools: list[dict[str, Any]] = []
    page = 1
    with httpx.Client(timeout=_TIMEOUT) as client:
        while True:
            resp = get_json(
                client,
                f"{_RAYDIUM_URL}/pools/info/list",
                {
                    "poolType": "all",
                    "poolSortField": "volume24h",
                    "sortType": "desc",
                    "pageSize": 1000,
                    "page": page,
                },
            )
            data = resp.get("data", {})
            batch = data.get("data", [])
            all_pools.extend(batch)
            # sorted desc, so once the lowest pool on the page is below the floor we can stop
            below_floor = batch and (batch[-1].get("day", {}).get("volume") or 0) < _VOLUME_FLOOR
            if below_floor or not data.get("hasNextPage", False):
                break
            page += 1
            if page > _MAX_PAGES:
                logger.warning("raydium_max_pages_reached", max_pages=_MAX_PAGES)
                break
    logger.info("raydium_fetch_complete", pool_count=len(all_pools), pages=page)
    return {"pools": all_pools}


def parse_raydium(
    response: dict[str, Any], snapshot_at: datetime, snapshot_date: date, source_file: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pool in response.get("pools", []):
        pool_address = pool.get("id")  # Raydium uses "id", not "address"
        if not pool_address:
            logger.warning("raydium_pool_missing_id", pool_keys=list(pool.keys()))
            continue
        mint_a: dict[str, Any] = pool.get("mintA") or {}
        mint_b: dict[str, Any] = pool.get("mintB") or {}
        day: dict[str, Any] = pool.get("day") or {}
        volume, tvl = day.get("volume"), pool.get("tvl")
        if not _keep(volume, tvl):
            continue
        rows.append(
            {
                "snapshot_at": snapshot_at,
                "snapshot_date": snapshot_date,
                "dex_name": "raydium",
                "pool_address": pool_address,
                "base_token_symbol": mint_a.get("symbol"),
                "base_token_address": mint_a.get("address"),
                "quote_token_symbol": mint_b.get("symbol"),
                "quote_token_address": mint_b.get("address"),
                "trailing_24h_volume_usd": volume,
                "trailing_24h_fees_usd": day.get("volumeFee"),
                "tvl_usd": tvl,
                "source_file": source_file,
            }
        )
    return rows


# Orca — https://api.orca.so
_ORCA_URL = "https://api.orca.so"
_ORCA_PAGE_SIZE = 50  # the API caps each page at 50 regardless of the limit we ask for
_ORCA_MAX_PAGES = 1000  # safety ceiling; real stop is the volume floor / cursor / no-new check


def _orca_volume(pool: dict[str, Any]) -> float:
    return _to_float((pool.get("stats") or {}).get("24h", {}).get("volume")) or 0


def fetch_orca() -> dict[str, Any]:
    """Page through Orca Whirlpools (sorted by volume desc) down to the volume floor.

    Cursor pagination via the ``after`` param, deduped by address. At the end of the
    data the API repeats the last cursor, so we also stop once a page adds nothing new.
    """
    all_pools: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor: str | None = None
    pages = 0
    with httpx.Client(timeout=_TIMEOUT) as client:
        while True:
            params: dict[str, Any] = {"limit": _ORCA_PAGE_SIZE}
            if cursor:
                params["after"] = cursor
            resp = get_json(client, f"{_ORCA_URL}/v2/solana/pools", params)
            batch = resp.get("data", [])
            new_this_page = 0
            for pool in batch:
                addr = pool.get("address")
                if addr and addr not in seen:
                    seen.add(addr)
                    all_pools.append(pool)
                    new_this_page += 1
            pages += 1
            cursor = resp.get("meta", {}).get("cursor", {}).get("next")
            # sorted desc, so stop once the lowest pool on the page is below the floor
            below_floor = batch and _orca_volume(batch[-1]) < _VOLUME_FLOOR
            if below_floor or not cursor or new_this_page == 0:
                break
            if pages >= _ORCA_MAX_PAGES:
                logger.warning("orca_max_pages_reached", max_pages=_ORCA_MAX_PAGES)
                break
    logger.info("orca_fetch_complete", pool_count=len(all_pools), pages=pages)
    return {"pools": all_pools}


def parse_orca(
    response: dict[str, Any], snapshot_at: datetime, snapshot_date: date, source_file: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pool in response.get("pools", []):
        pool_address = pool.get("address")
        if not pool_address:
            logger.warning("orca_pool_missing_address", pool_keys=list(pool.keys()))
            continue
        token_a: dict[str, Any] = pool.get("tokenA") or {}  # Orca uses tokenA/tokenB
        token_b: dict[str, Any] = pool.get("tokenB") or {}
        stats_24h: dict[str, Any] = (pool.get("stats") or {}).get("24h") or {}
        volume, tvl = _to_float(stats_24h.get("volume")), _to_float(pool.get("tvlUsdc"))
        if not _keep(volume, tvl):
            continue
        rows.append(
            {
                "snapshot_at": snapshot_at,
                "snapshot_date": snapshot_date,
                "dex_name": "orca",
                "pool_address": pool_address,
                "base_token_symbol": token_a.get("symbol"),
                "base_token_address": token_a.get("address"),
                "quote_token_symbol": token_b.get("symbol"),
                "quote_token_address": token_b.get("address"),
                "trailing_24h_volume_usd": volume,
                "trailing_24h_fees_usd": _to_float(stats_24h.get("fees")),
                "tvl_usd": tvl,
                "source_file": source_file,
            }
        )
    return rows


# Meteora — https://amm-v2.meteora.ag
_METEORA_URL = "https://amm-v2.meteora.ag"
_METEORA_PAGE_SIZE = 300  # API enforces a hard cap of 300 per page


def fetch_meteora() -> dict[str, Any]:
    """Page through Meteora DAMM V2 pools (sorted by volume desc) down to the volume floor."""
    all_pools: list[dict[str, Any]] = []
    page = 0
    with httpx.Client(timeout=_TIMEOUT) as client:
        while True:
            resp = get_json(
                client, f"{_METEORA_URL}/pools/search", {"page": page, "size": _METEORA_PAGE_SIZE}
            )
            batch = resp.get("data", [])
            all_pools.extend(batch)
            total_count: int = resp.get("total_count", 0)
            page += 1
            # sorted desc, so stop once the lowest pool on the page is below the floor
            below_floor = (
                batch and (_to_float(batch[-1].get("trading_volume")) or 0) < _VOLUME_FLOOR
            )
            if below_floor or len(all_pools) >= total_count:
                break
            if page >= _MAX_PAGES:
                logger.warning("meteora_max_pages_reached", max_pages=_MAX_PAGES)
                break
    logger.info("meteora_fetch_complete", pool_count=len(all_pools), pages=page)
    return {"pools": all_pools}


def _meteora_symbols(pool_name: str | None) -> tuple[str | None, str | None]:
    """Split 'SOL-USDC' into ('SOL', 'USDC').

    Meteora embeds symbols in pool_name with a '-' separator. Names starting with
    '-' have no registered base symbol, so base returns 'UNKNOWN'.
    """
    if not pool_name or "-" not in pool_name:
        return None, None
    base, _, quote = pool_name.partition("-")
    return base if base else "UNKNOWN", quote or None


def parse_meteora(
    response: dict[str, Any], snapshot_at: datetime, snapshot_date: date, source_file: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pool in response.get("pools", []):
        pool_address = pool.get("pool_address")
        if not pool_address:
            logger.warning("meteora_pool_missing_address", pool_keys=list(pool.keys()))
            continue
        # Meteora returns pool_tvl as a string — coerce so BQ gets a real float
        volume, tvl = _to_float(pool.get("trading_volume")), _to_float(pool.get("pool_tvl"))
        if not _keep(volume, tvl):
            continue
        mints: list[str] = pool.get("pool_token_mints") or []
        base_symbol, quote_symbol = _meteora_symbols(pool.get("pool_name"))
        rows.append(
            {
                "snapshot_at": snapshot_at,
                "snapshot_date": snapshot_date,
                "dex_name": "meteora",
                "pool_address": pool_address,
                "base_token_symbol": base_symbol,
                "base_token_address": mints[0] if len(mints) > 0 else None,
                "quote_token_symbol": quote_symbol,
                "quote_token_address": mints[1] if len(mints) > 1 else None,
                "trailing_24h_volume_usd": volume,
                "trailing_24h_fees_usd": pool.get("fee_volume"),
                "tvl_usd": tvl,
                "source_file": source_file,
            }
        )
    return rows


# DefiLlama (market share) — https://api.llama.fi
_DEFILLAMA_URL = "https://api.llama.fi"
_INCLUDED_PROTOCOLS = {"raydium", "orca", "meteora"}


def fetch_market_share() -> dict[str, Any]:
    """Fetch Solana DEX volume data from DefiLlama (single response, no paging)."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = get_json(
            client,
            f"{_DEFILLAMA_URL}/overview/dexs/solana",
            {
                "excludeTotalDataChart": "true",
                "excludeTotalDataChartBreakdown": "true",
            },
        )
    logger.info("defillama_fetch_complete", protocol_count=len(resp.get("protocols", [])))
    return resp


def parse_market_share(
    response: dict[str, Any], snapshot_at: datetime, snapshot_date: date, source_file: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proto in response.get("protocols", []):
        name: str = proto.get("name") or ""
        if not any(t in name.lower() for t in _INCLUDED_PROTOCOLS):
            continue
        rows.append(
            {
                "snapshot_at": snapshot_at,
                "snapshot_date": snapshot_date,
                "dex_name": name.lower(),
                "trailing_24h_volume_usd": proto.get("total24h"),
                "trailing_7d_volume_usd": proto.get("total7d"),
                "total_volume_usd": proto.get("totalAllTime"),
                "source_file": source_file,
            }
        )
    logger.info("defillama_parse_complete", row_count=len(rows))
    return rows
