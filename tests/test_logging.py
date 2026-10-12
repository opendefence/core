"""Test the logging stuff"""

import datetime
import json
import logging
import re
from typing import Any

import pytest

from lib_opendefence_core.logging import AUDIT, DEFAULT_LOG_FORMAT, TRACE, add_trace_and_audit, get_logger, init_logging
from lib_opendefence_core.logging.common import AddExtrasFilter
from lib_opendefence_core.logging.levels import RAISE, add_logging_level


@pytest.mark.parametrize("name", [__name__, None])
def test_get_logger(name: str | None, caplog: pytest.LogCaptureFixture) -> None:
    existing = logging.getLogger(name)
    logger = get_logger(name)
    assert logger is existing
    assert get_logger(name) is logger

    with caplog.at_level(TRACE):
        logger.trace("Tracing")
        logger.audit("User %s enrolled", "alice", extra={"actor": "alice"})

    assert [record.levelno for record in caplog.records] == [TRACE, AUDIT]
    assert caplog.records[1].getMessage() == "User alice enrolled"
    assert caplog.records[1].__dict__["actor"] == "alice"
    assert caplog.records[1].funcName == "test_get_logger"


@pytest.mark.parametrize("method", ["trace", "audit"])
def test_get_logger_rejects_missing_methods(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    logger = get_logger(__name__)
    monkeypatch.setattr(logger, method, None)
    with pytest.raises(TypeError, match="does not support AUDIT and TRACE"):
        get_logger(__name__)


@pytest.mark.parametrize(
    ("target", "attribute"),
    [(logging, "TRACE"), (logging, "trace"), (logging.Logger, "trace"), (logging.LoggerAdapter, "trace")],
)
def test_partial_registration_raises(monkeypatch: pytest.MonkeyPatch, target: Any, attribute: str) -> None:
    add_trace_and_audit()
    monkeypatch.delattr(target, attribute)

    with pytest.raises(AttributeError, match="partially configured"):
        add_logging_level("TRACE", logging.DEBUG - 5, if_exists=RAISE)

    assert not hasattr(target, attribute)


def test_complete_registration_allows_raise_policy() -> None:
    add_trace_and_audit()
    add_logging_level("TRACE", logging.DEBUG - 5, if_exists=RAISE)
    assert logging.getLevelName(logging.DEBUG - 5) == "TRACE"


@pytest.mark.parametrize("key", ["msg", "args", "levelno", "levelname", "created", "message", "asctime"])
def test_global_labels_reject_record_attributes(key: str) -> None:
    with pytest.raises(ValueError, match="log record attributes"):
        AddExtrasFilter({key: "overwritten"})


def test_global_labels_preserve_record_after_input_changes() -> None:
    extras = {"deployment": "core"}
    label_filter = AddExtrasFilter(extras)
    extras["msg"] = "overwritten"
    record = logging.LogRecord("test", logging.WARNING, __file__, 1, "User %s", ("alice",), None)

    assert label_filter.filter(record)
    assert record.getMessage() == "User alice"
    assert record.__dict__["deployment"] == "core"


@pytest.mark.parametrize("level", ["trace", "audit"])
@pytest.mark.parametrize("target", ["logger", "adapter", "module"])
@pytest.mark.parametrize("stacklevel", [None, 1, 2])
def test_custom_level_caller(caplog: pytest.LogCaptureFixture, level: str, target: str, stacklevel: int | None) -> None:
    add_trace_and_audit()
    logger = get_logger(__name__)
    loggers = {"logger": logger, "adapter": logging.LoggerAdapter(logger, {}), "module": logging}
    log = getattr(loggers[target], level)

    def helper() -> None:
        if stacklevel is None:
            log("caller attribution")
        else:
            log("caller attribution", stacklevel=stacklevel)

    with caplog.at_level(logging.DEBUG - 5):
        helper()

    assert len(caplog.records) == 1
    assert caplog.records[0].pathname == __file__
    assert caplog.records[0].funcName == ("test_custom_level_caller" if stacklevel == 2 else "helper")


def test_log_format() -> None:
    """Check that the default format contains some things we want"""
    assert "pathname" in DEFAULT_LOG_FORMAT
    assert "funcName" in DEFAULT_LOG_FORMAT
    assert "lineno" in DEFAULT_LOG_FORMAT
    assert "asctime" in DEFAULT_LOG_FORMAT


# FIXME: What is the correct type hint for monkeypatch ??
def test_logging_init(monkeypatch: Any) -> None:
    """Test that ini_logging does not explode"""
    monkeypatch.setenv("LOG_GLOBAL_LABELS_JSON", '{"globaltag": "the value", "another_global_tag": "ditto"}')
    init_logging(logging.DEBUG)


# FIXME: What is the correct type hint for monkeypatch ??
# FIXME: what is the correct type for capsys ??
def test_logging_ecs(capsys: Any, monkeypatch: Any) -> None:
    """Check that we got all level of messages to capsys"""
    now = datetime.datetime.now(datetime.UTC)
    monkeypatch.setenv("LOG_GLOBAL_LABELS_JSON", '{"hierarchical.tag.value": "get", "another_global_tag": "ditto"}')
    add_trace_and_audit()
    # we must explicitly init again due to capsys
    init_logging(TRACE)
    logger = get_logger(__name__)
    logger.trace("Test message trace")
    logger.debug("Test message debug")
    logger.info("Test message info")
    logger.warning("Test message warn")
    logger.error("Test message error")
    logger.audit("Test message audit")

    # Check that the log lines start as expected
    (_, stderr) = capsys.readouterr()
    for line, level in zip(stderr.splitlines(), ("trace", "debug", "info", "warning", "error", "audit"), strict=True):
        parsed = json.loads(line)
        assert parsed["log.level"] == level
        msgtime = datetime.datetime.fromisoformat(parsed["@timestamp"].replace("Z", "+00:00"))
        assert msgtime - now < datetime.timedelta(seconds=5)


def test_logging_oldskool(capsys: Any, monkeypatch: Any) -> None:
    """Check that we got all level of messages to capsys"""
    monkeypatch.setenv("LOG_GLOBAL_LABELS_JSON", '{"hierarchical.tag.value": "get", "another_global_tag": "ditto"}')
    monkeypatch.setenv("LOG_CONSOLE_FORMATTER", "utc")
    add_trace_and_audit()
    # we must explicitly init again due to capsys
    init_logging(TRACE)
    isots_thismin_regex = (
        r"^\[" + re.escape(datetime.datetime.now(datetime.UTC).isoformat()[:17]) + r"[0-9]{2}\.[0-9]{3}Z\]"
    )
    logger = get_logger(__name__)
    logger.trace("Test message trace")
    logger.debug("Test message debug")
    logger.info("Test message info")
    logger.warning("Test message warn")
    logger.error("Test message error")
    logger.audit("Test message audit")

    # Check that the log lines start as expected
    (_, stderr) = capsys.readouterr()
    assert re.search(isots_thismin_regex + re.escape("[TRACE]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[DEBUG]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[INFO]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[WARNING]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[ERROR]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[AUDIT]"), stderr, flags=re.MULTILINE)
