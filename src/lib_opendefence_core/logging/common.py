"""Things common for all handlers"""

import datetime
import logging.config
import time
from collections.abc import Mapping
from typing import Any, override

import ecs_logging


class UTCISOFormatter(logging.Formatter):
    """Output timestamps in UTC ISO timestamps"""

    converter = time.gmtime  # type: ignore[assignment]  # false positive

    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        converted = datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC)
        if datefmt:
            formatted = converted.strftime(datefmt)
        else:
            formatted = converted.isoformat(timespec="milliseconds")
        return formatted.replace("+00:00", "Z")


DEFAULT_LOG_FORMAT = (
    "[%(asctime)s][%(levelname)s] %(name)s (%(process)d) %(pathname)s:%(funcName)s:%(lineno)d | %(message)s"
)
DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "ecs": {
            "()": ecs_logging.StdlibFormatter,
        },
        "utc": {
            "()": UTCISOFormatter,
            "format": DEFAULT_LOG_FORMAT,
        },
        "local": {
            "format": DEFAULT_LOG_FORMAT,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "ecs",
        },
    },
    "root": {
        "handlers": ["console"],
    },
}

DEFAULT_RECORD_DIR = set(dir(logging.LogRecord("dummy", 10, "dummy.py", 228, "Dummy", None, None, "dummy", None))) | {
    "message",
    "asctime",
}


class AddExtrasFilter(logging.Filter):  # pylint: disable=R0903
    """Add the extra properties and values given at init"""

    def __init__(self, extras: Mapping[str, Any], name: str = "") -> None:
        """init"""
        if not extras or not isinstance(extras, Mapping):
            raise ValueError("extras must be non-empty mapping")
        self.add_extras = dict(extras)
        if reserved := DEFAULT_RECORD_DIR.intersection(self.add_extras):
            raise ValueError(f"extras must not overwrite log record attributes: {', '.join(sorted(reserved))}")
        super().__init__(name)

    @override
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        """Add the extras then call parent filter"""
        for key in self.add_extras:
            setattr(record, key, self.add_extras[key])
        return super().filter(record)
