from typing import Any

from src.sources.base import BaseSourceClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.orca.so"
_PAGE_SIZE = 200
_DEFAULT_MAX_PAGES = 50


class OrcaClient(BaseSourceClient):
    """Fetches all Orca Whirlpool pools via cursor-based pagination.

    The API returns ``meta.cursor.next`` (a base58 string) as the next-page
    token; absence of this key (or None value) signals the last page.

    DEVIATION: stats.24h.volume, stats.24h.fees, and tvlUsdc are returned as
    high-precision decimal strings in the JSON, not numbers. The parser casts
    them to float.
    """

    def __init__(self, timeout: int = 30, max_pages: int = _DEFAULT_MAX_PAGES) -> None:
        super().__init__(base_url=_BASE_URL, timeout=timeout)
        self._max_pages = max_pages

    @property
    def dex_name(self) -> str:
        return "orca"

    def fetch(self) -> dict[str, Any]:
        all_pools: list[dict[str, Any]] = []
        seen_addresses: set[str] = set()
        cursor: str | None = None
        pages = 0
        while True:
            params: dict[str, Any] = {"limit": _PAGE_SIZE}
            if cursor:
                params["cursor"] = cursor
            resp = self._get_with_retry(
                f"{self._base_url}/v2/solana/pools", params=params
            )
            for pool in resp.get("data", []):
                addr = pool.get("address")
                if addr and addr not in seen_addresses:
                    seen_addresses.add(addr)
                    all_pools.append(pool)
            pages += 1
            cursor = (
                resp.get("meta", {}).get("cursor", {}).get("next")
            )
            if not cursor:
                break
            if pages >= self._max_pages:
                logger.warning("orca_max_pages_reached", max_pages=self._max_pages)
                break
        logger.info("orca_fetch_complete", pool_count=len(all_pools), pages=pages)
        return {"pools": all_pools}
