from typing import Any

from src.sources.base import BaseSourceClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.llama.fi"


class DefiLlamaClient(BaseSourceClient):
    """Fetches Solana DEX volume data from the DefiLlama overview endpoint.

    Returns a single response (no pagination) containing per-protocol
    trailing volume metrics for all Solana DEXs.
    """

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(base_url=_BASE_URL, timeout=timeout)

    @property
    def dex_name(self) -> str:
        return "defillama"

    def fetch(self) -> dict[str, Any]:
        resp = self._get_with_retry(
            f"{self._base_url}/overview/dexs/solana",
            params={
                "excludeTotalDataChart": "true",
                "excludeTotalDataChartBreakdown": "true",
            },
        )
        protocol_count = len(resp.get("protocols", []))
        logger.info("defillama_fetch_complete", protocol_count=protocol_count)
        return resp
