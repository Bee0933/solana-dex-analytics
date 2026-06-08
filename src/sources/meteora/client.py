from typing import Any

from src.sources.base import BaseSourceClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://amm-v2.meteora.ag"
_PAGE_SIZE = 300  # API enforces a hard cap of 300 per page; 400 above that
_DEFAULT_MAX_PAGES = 50


class MeteoraClient(BaseSourceClient):
    """Fetches Meteora Dynamic AMM V2 pools via page-based pagination.

    DEVIATION from spec: ``/pools`` requires an address param and is not a
    list endpoint. The correct list endpoint is ``/pools/search`` which returns
    ``{ data: [...], page: int, total_count: int }``.
    """

    def __init__(self, timeout: int = 30, max_pages: int = _DEFAULT_MAX_PAGES) -> None:
        super().__init__(base_url=_BASE_URL, timeout=timeout)
        self._max_pages = max_pages

    @property
    def dex_name(self) -> str:
        return "meteora"

    def fetch(self) -> dict[str, Any]:
        all_pools: list[dict[str, Any]] = []
        page = 0
        while True:
            resp = self._get_with_retry(
                f"{self._base_url}/pools/search",
                params={"page": page, "size": _PAGE_SIZE},
            )
            batch = resp.get("data", [])
            all_pools.extend(batch)
            total_count: int = resp.get("total_count", 0)
            page += 1
            if len(all_pools) >= total_count:
                break
            if page >= self._max_pages:
                logger.warning("meteora_max_pages_reached", max_pages=self._max_pages)
                break
        logger.info("meteora_fetch_complete", pool_count=len(all_pools), pages=page)
        return {"pools": all_pools}
