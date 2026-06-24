import logging
import os
import sys
from typing import Any, cast

import structlog
from structlog.types import FilteringBoundLogger

# structlog level name -> Cloud Logging severity
_SEVERITY = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "warn": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
    "exception": "ERROR",
}


def _cloud_logging_processor(
    _logger: Any, _name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    # Cloud Logging parses JSON fields "severity" and "message" natively.
    level = event_dict.pop("level", "info")
    event_dict["severity"] = _SEVERITY.get(level, "INFO")
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    # wire Python's built-in logging to stdout so Cloud Run can capture it
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    is_prod = os.getenv("ENVIRONMENT", "local") == "prod"

    # These processors run on every log call before the final renderer gets it
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # In prod: map to Cloud Logging severity/message, then emit JSON.
    # Locally: pretty console renderer for readability.
    renderer: list[Any]
    if is_prod:
        renderer = [_cloud_logging_processor, structlog.processors.JSONRenderer()]
    else:
        renderer = [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=[*shared_processors, *renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind the Cloud Run execution identity to every log line for correlation.
    structlog.contextvars.bind_contextvars(
        run_id=os.getenv("CLOUD_RUN_EXECUTION", "local"),
        task_attempt=os.getenv("CLOUD_RUN_TASK_ATTEMPT", "0"),
    )


def bind_context(**kwargs: Any) -> None:
    # add fields to every subsequent log line in this run (e.g. snapshot_date, dex)
    structlog.contextvars.bind_contextvars(**kwargs)


def get_logger(name: str) -> FilteringBoundLogger:
    return cast(FilteringBoundLogger, structlog.get_logger(name))
