import time
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    # retry on server errors and rate limits, not on bad requests (404, 403 etc.)
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, httpx.TransportError)


class BaseSourceClient(ABC):
    def __init__(self, base_url: str, timeout: int = 30) -> None:
        # store the base url and open an http connection ready to use
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    @property
    @abstractmethod
    def dex_name(self) -> str: ...  # every subclass must declare its name

    @abstractmethod
    def fetch(self) -> dict[str, Any]: ...  # every subclass must implement its own fetch

    @retry(
        stop=stop_after_attempt(3),            # try at most 3 times
        wait=wait_exponential(multiplier=1, min=2, max=30),  # wait 2s, 4s, up to 30s
        retry=retry_if_exception(_is_retryable),  # only retry if the error is worth retrying
        reraise=True,                          # if all 3 fail, raise the original error
    )
    def _get_with_retry(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        response = self._client.get(url, params=params)
        latency_ms = (time.monotonic() - t0) * 1000

        # log every request so we can monitor speed and catch problems
        logger.info(
            "http_get",
            url=url,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 1),
            response_bytes=len(response.content),
        )

        # throw an exception if the server returned an error — triggers retry logic above
        response.raise_for_status()

        # parse the response body from JSON and return it as a python dict
        return cast(dict[str, Any], response.json())


class BaseSourceParser(ABC):
    @abstractmethod
    def parse(
        self,
        response: dict[str, Any],
        snapshot_at: datetime,
        snapshot_date: date,
        source_file: str,
    ) -> list[dict[str, Any]]: ...  # every subclass must map its API fields to our schema
