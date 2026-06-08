from datetime import date, datetime
from typing import Any

from src.sources.base import BaseSourceParser
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Protocols whose names contain any of these substrings are included.
# Meteora has multiple protocol entries (DLMM, DAMM V1, DAMM V2, DBC) which
# all match "meteora" — they are kept as separate rows.
_INCLUDED_PROTOCOLS = {"raydium", "orca", "meteora"}


def _is_included(name: str) -> bool:
    name_lower = name.lower()
    return any(t in name_lower for t in _INCLUDED_PROTOCOLS)


class DefiLlamaParser(BaseSourceParser):
    """Maps DefiLlama protocol entries to the raw_dex_market_share schema.

    NOTE: This parser returns rows for raw_dex_market_share (not raw_dex_pools).
    The output schema differs from the other parsers.

    Field mapping confirmed against api.llama.fi/overview/dexs/solana:
      dex_name                ← name.lower()
      trailing_24h_volume_usd ← total24h    (nullable per protocol)
      trailing_7d_volume_usd  ← total7d
      total_volume_usd        ← totalAllTime
    """

    def parse(
        self,
        response: dict[str, Any],
        snapshot_at: datetime,
        snapshot_date: date,
        source_file: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for proto in response.get("protocols", []):
            name: str = proto.get("name") or ""
            if not _is_included(name):
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
