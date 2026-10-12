"""Logging helpers"""

import copy
import json
import logging
import logging.config
import os
from typing import TYPE_CHECKING, Any, cast

from .common import DEFAULT_LOG_FORMAT, DEFAULT_LOGGING_CONFIG, AddExtrasFilter, UTCISOFormatter
from .levels import add_logging_level

TRACE = logging.DEBUG - 5
AUDIT = logging.CRITICAL + 5

if TYPE_CHECKING:

    class Logger(logging.Logger):
        """Describe the methods installed by level registration."""

        audit = logging.Logger.info
        trace = logging.Logger.debug
else:
    Logger = logging.Logger


def add_trace_and_audit() -> None:
    """Adds TRACE (less important than DEBUG) and AUDIT (more important than critical) levels"""
    add_logging_level("TRACE", TRACE)
    add_logging_level("AUDIT", AUDIT)


def get_logger(name: str | None = None) -> Logger:
    """Return a standard logger with typed TRACE and AUDIT methods."""
    add_trace_and_audit()
    logger = logging.getLogger(name)
    if not callable(getattr(logger, "audit", None)) or not callable(getattr(logger, "trace", None)):
        raise TypeError("Logger does not support AUDIT and TRACE")
    return cast(Logger, logger)


def init_logging(level: int = logging.INFO) -> None:
    """Initialize logging, call this if you don't know any better logging arrangements"""
    labels_json = os.environ.get("LOG_GLOBAL_LABELS_JSON")
    console_formatter = os.environ.get("LOG_CONSOLE_FORMATTER", "ecs")
    config = cast(dict[str, Any], copy.deepcopy(DEFAULT_LOGGING_CONFIG))
    # If we have the labels env set, apply filter that sets these labels to all log records
    if labels_json:
        config["filters"] = {
            "global_labels": {
                "()": AddExtrasFilter,
                "extras": json.loads(labels_json),
            },
        }
        for key in config["handlers"]:
            if "filters" not in config["handlers"][key]:
                config["handlers"][key]["filters"] = []
            config["handlers"][key]["filters"].append("global_labels")
    # Set root loglevel to desired
    config["root"]["level"] = level
    config["handlers"]["console"]["formatter"] = console_formatter
    logging.config.dictConfig(config)


__all__ = [
    "AUDIT",
    "DEFAULT_LOGGING_CONFIG",
    "DEFAULT_LOG_FORMAT",
    "TRACE",
    "Logger",
    "UTCISOFormatter",
    "add_trace_and_audit",
    "get_logger",
    "init_logging",
]
