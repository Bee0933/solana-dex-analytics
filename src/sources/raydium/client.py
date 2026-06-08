from typing import Any

from src.sources.base import BaseSourceClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api-v3.raydium.io"
_PAGE_SIZE = 1000
_DEFAULT_MAX_PAGES = 50


class RaydiumClient(BaseSourceClient):
    """Fetches all pools from the Raydium v3 API, sorted by 24h volume desc.

    The API paginates via page/pageSize params and signals the last page with
    ``data.hasNextPage == False``.
    """

    def __init__(self, timeout: int = 30, max_pages: int = _DEFAULT_MAX_PAGES) -> None:
        super().__init__(base_url=_BASE_URL, timeout=timeout)
        self._max_pages = max_pages

    @property
    def dex_name(self) -> str:
        return "raydium"

    def fetch(self) -> dict[str, Any]:
        all_pools: list[dict[str, Any]] = []
        page = 1
        while True:
            resp = self._get_with_retry(
                f"{self._base_url}/pools/info/list",
                params={
                    "poolType": "all",
                    "poolSortField": "volume24h",
                    "sortType": "desc",
                    "pageSize": _PAGE_SIZE,
                    "page": page,
                },
            )
            data = resp.get("data", {})
            all_pools.extend(data.get("data", []))
            if not data.get("hasNextPage", False):
                break
            page += 1
            if page > self._max_pages:
                logger.warning("raydium_max_pages_reached", max_pages=self._max_pages)
                break
        logger.info("raydium_fetch_complete", pool_count=len(all_pools), pages=page)
        return {"pools": all_pools}
