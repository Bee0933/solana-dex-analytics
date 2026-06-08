from datetime import date, datetime
from typing import Any

from src.sources.base import BaseSourceParser
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _to_float(val: Any) -> float | None:
    """Cast to float; returns None on failure.

    Orca returns stats and TVL values as high-precision decimal strings
    (e.g. "122201862.92057900"), not JSON numbers.
    """
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class OrcaParser(BaseSourceParser):
    """Maps Orca Whirlpool pool objects to the unified raw_dex_pools schema.

    Field mapping confirmed against api.orca.so/v2/solana/pools response:
      pool_address            ← pool["address"]
      base_token_symbol       ← tokenA.symbol
      base_token_address      ← tokenA.address
      quote_token_symbol      ← tokenB.symbol
      quote_token_address     ← tokenB.address
      trailing_24h_volume_usd ← stats["24h"]["volume"]   (string → float)
      trailing_24h_fees_usd   ← stats["24h"]["fees"]      (string → float)
      tvl_usd                 ← tvlUsdc                   (string → float)

    DEVIATION from spec: Orca uses tokenA/tokenB (not mintA/mintB).
    DEVIATION: stats["24h"] is keyed by the string "24h", not an attribute.
    """

    def parse(
        self,
        response: dict[str, Any],
        snapshot_at: datetime,
        snapshot_date: date,
        source_file: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pool in response.get("pools", []):
            pool_address = pool.get("address")
            if not pool_address:
                logger.warning("orca_pool_missing_address", pool_keys=list(pool.keys()))
                continue
            token_a: dict[str, Any] = pool.get("tokenA") or {}
            token_b: dict[str, Any] = pool.get("tokenB") or {}
            stats_24h: dict[str, Any] = (pool.get("stats") or {}).get("24h") or {}
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
                    "trailing_24h_volume_usd": _to_float(stats_24h.get("volume")),
                    "trailing_24h_fees_usd": _to_float(stats_24h.get("fees")),
                    "tvl_usd": _to_float(pool.get("tvlUsdc")),
                    "source_file": source_file,
                }
            )
        return rows
