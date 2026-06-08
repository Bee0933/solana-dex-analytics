from datetime import date, datetime
from typing import Any

from src.sources.base import BaseSourceParser
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_symbols(pool_name: str | None) -> tuple[str | None, str | None]:
    """Split 'SOL-USDC' into ('SOL', 'USDC').

    Meteora does not return token symbols as separate fields; they are embedded
    in pool_name with a '-' separator (e.g. 'SOL-JitoSOL', 'USDC-USDT').
    Multi-token pools or unexpected formats return (None, None).
    """
    if not pool_name or "-" not in pool_name:
        return None, None
    base, _, quote = pool_name.partition("-")
    return base or None, quote or None


class MeteoraParser(BaseSourceParser):
    """Maps Meteora DAMM V2 pool objects to the unified raw_dex_pools schema.

    Field mapping confirmed against amm-v2.meteora.ag/pools/search response:
      pool_address            ← pool_address
      base_token_symbol       ← parsed from pool_name (left of first "-")
      base_token_address      ← pool_token_mints[0]
      quote_token_symbol      ← parsed from pool_name (right of first "-")
      quote_token_address     ← pool_token_mints[1]
      trailing_24h_volume_usd ← trading_volume   (24h window confirmed)
      trailing_24h_fees_usd   ← fee_volume        (24h window confirmed)
      tvl_usd                 ← pool_tvl
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
            pool_address = pool.get("pool_address")
            if not pool_address:
                logger.warning(
                    "meteora_pool_missing_address", pool_keys=list(pool.keys())
                )
                continue
            mints: list[str] = pool.get("pool_token_mints") or []
            base_symbol, quote_symbol = _parse_symbols(pool.get("pool_name"))
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
                    "trailing_24h_volume_usd": pool.get("trading_volume"),
                    "trailing_24h_fees_usd": pool.get("fee_volume"),
                    "tvl_usd": pool.get("pool_tvl"),
                    "source_file": source_file,
                }
            )
        return rows
