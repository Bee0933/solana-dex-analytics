import logging
import os
import sys
from typing import Any, cast

import structlog
from structlog.types import FilteringBoundLogger


def configure_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    # wire Python's built-in logging to stdout so Prefect and Cloud Run can capture it
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    # These processors run on every log call before the final renderer gets it
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,   # inject any context set earlier in the request
        structlog.processors.add_log_level,        # add "level" key to the log dict
        structlog.processors.TimeStamper(fmt="iso"), # add an ISO timestamp
        structlog.processors.StackInfoRenderer(),  # include stack info on errors
    ]

    # In prod we emit JSON so Cloud Logging can parse each field individually.
    # Locally we use the pretty console renderer so it is readable during development.
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if os.getenv("ENVIRONMENT", "local") == "prod"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level), # respect the log level
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True, # build the processor chain once, not on every call
    )


def get_logger(name: str) -> FilteringBoundLogger:
    return cast(FilteringBoundLogger, structlog.get_logger(name))
