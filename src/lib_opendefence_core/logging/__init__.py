"""Logging helpers"""

from typing import Dict, Any, cast
import logging
import logging.config
import copy
import os
import json


from .common import DEFAULT_LOGGING_CONFIG, UTCISOFormatter, DEFAULT_LOG_FORMAT, AddExtrasFilter
from .levels import add_logging_level


def add_trace_and_audit() -> None:
    """Adds TRACE (less important than DEBUG) and AUDIT (more important than critical) levels"""
    add_logging_level("TRACE", logging.DEBUG - 5)
    add_logging_level("AUDIT", logging.CRITICAL + 5)


def init_logging(level: int = logging.INFO) -> None:
    """Initialize logging, call this if you don't know any better logging arrangements"""
    labels_json = os.environ.get("LOG_GLOBAL_LABELS_JSON")
    console_formatter = os.environ.get("LOG_CONSOLE_FORMATTER", "ecs")
    config = cast(Dict[str, Any], copy.deepcopy(DEFAULT_LOGGING_CONFIG))
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


__all__ = ["DEFAULT_LOG_FORMAT", "UTCISOFormatter", "DEFAULT_LOGGING_CONFIG", "init_logging", "add_trace_and_audit"]
