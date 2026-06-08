from datetime import date, datetime
from typing import Any

from src.sources.base import BaseSourceParser
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RaydiumParser(BaseSourceParser):
    """Maps Raydium pool objects to the unified raw_dex_pools schema.

    Field mapping confirmed against api-v3.raydium.io/pools/info/list response:
      pool_address          ← pool["id"]            (Raydium uses "id" not "address")
      base_token_symbol     ← mintA.symbol
      base_token_address    ← mintA.address
      quote_token_symbol    ← mintB.symbol
      quote_token_address   ← mintB.address
      trailing_24h_volume_usd ← day.volume
      trailing_24h_fees_usd   ← day.volumeFee
      tvl_usd               ← tvl
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
            pool_address = pool.get("id")
            if not pool_address:
                logger.warning("raydium_pool_missing_id", pool_keys=list(pool.keys()))
                continue
            mint_a: dict[str, Any] = pool.get("mintA") or {}
            mint_b: dict[str, Any] = pool.get("mintB") or {}
            day: dict[str, Any] = pool.get("day") or {}
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
                    "trailing_24h_volume_usd": day.get("volume"),
                    "trailing_24h_fees_usd": day.get("volumeFee"),
                    "tvl_usd": pool.get("tvl"),
                    "source_file": source_file,
                }
            )
        return rows
