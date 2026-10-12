"""Test the logging stuff"""

from typing import Any
import logging
import datetime
import json
import re

from lib_opendefence_core.logging import DEFAULT_LOG_FORMAT, init_logging, add_trace_and_audit


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
    now = datetime.datetime.now(datetime.timezone.utc)
    monkeypatch.setenv("LOG_GLOBAL_LABELS_JSON", '{"hierarchical.tag.value": "get", "another_global_tag": "ditto"}')
    add_trace_and_audit()
    # we must explicitly init again due to capsys
    init_logging(logging.TRACE)  # type: ignore[attr-defined]  #  pylint: disable=E1101
    logging.getLogger(__name__).trace("Test message trace")  # type: ignore[attr-defined]  #  pylint: disable=E1101
    logging.getLogger(__name__).debug("Test message debug")
    logging.getLogger(__name__).info("Test message info")
    logging.getLogger(__name__).warning("Test message warn")
    logging.getLogger(__name__).error("Test message error")
    logging.getLogger(__name__).audit("Test message audit")  # type: ignore[attr-defined]  #  pylint: disable=E1101

    # Check that the log lines start as expected
    (_, stderr) = capsys.readouterr()
    for line, level in zip(stderr.splitlines(), ("trace", "debug", "info", "warning", "error", "audit")):
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
    init_logging(logging.TRACE)  # type: ignore[attr-defined]  #  pylint: disable=E1101
    isots_thismin_regex = r"^\[" + re.escape(datetime.datetime.utcnow().isoformat()[:17]) + r"[0-9]{2}\.[0-9]{3}Z\]"
    logging.getLogger(__name__).trace("Test message trace")  # type: ignore[attr-defined]  #  pylint: disable=E1101
    logging.getLogger(__name__).debug("Test message debug")
    logging.getLogger(__name__).info("Test message info")
    logging.getLogger(__name__).warning("Test message warn")
    logging.getLogger(__name__).error("Test message error")
    logging.getLogger(__name__).audit("Test message audit")  # type: ignore[attr-defined]  #  pylint: disable=E1101

    # Check that the log lines start as expected
    (_, stderr) = capsys.readouterr()
    assert re.search(isots_thismin_regex + re.escape("[TRACE]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[DEBUG]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[INFO]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[WARNING]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[ERROR]"), stderr, flags=re.MULTILINE)
    assert re.search(isots_thismin_regex + re.escape("[AUDIT]"), stderr, flags=re.MULTILINE)
