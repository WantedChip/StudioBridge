"""Unit tests for structured JSONL logging and secret redaction.

# req: LOG-01
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from studiobridge.core.logging import (
    JsonlFormatter,
    RedactingFilter,
    get_logger,
    redact_sensitive_data,
    redact_string,
    setup_logging,
)


def test_redact_hex_and_bearer_tokens():
    """Verify 256-bit hex secrets, bearer tokens, and key=value pairs are redacted.

    # req: LOG-01
    """
    hex_token = "4a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9"
    msg = f"Connecting with token={hex_token} and Bearer secret_jwt_token_here"
    redacted = redact_string(msg)

    assert hex_token not in redacted
    assert "secret_jwt_token_here" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_sensitive_data_nested_structures():
    """Verify recursive sanitization across dicts and lists.

    # req: LOG-01
    """
    payload = {
        "status": "ok",
        "secret": "super_secret_wire_key",
        "broker_token": "random_broker_token_123",
        "nested": {
            "password": "plain_password",
            "safe_field": 42,
            "items": ["safe", "token=hidden_val"],
        },
    }

    cleaned = redact_sensitive_data(payload)
    assert cleaned["status"] == "ok"
    assert cleaned["secret"] == "[REDACTED]"
    assert cleaned["broker_token"] == "[REDACTED]"
    assert cleaned["nested"]["password"] == "[REDACTED]"
    assert cleaned["nested"]["safe_field"] == 42
    assert "hidden_val" not in str(cleaned)


def test_jsonl_formatter_schema_fields():
    """Verify JSONL output strictly adheres to the standard 8-field schema.

    # req: LOG-01
    """
    formatter = JsonlFormatter()
    record = logging.LogRecord(
        name="studiobridge.wire",
        level=logging.INFO,
        pathname="wire.py",
        lineno=10,
        msg="Frame transmitted",
        args=(),
        exc_info=None,
    )
    record.comp = "wire"
    record.evt = "frame_sent"
    record.sid = "sess-1001"
    record.mid = 42
    record.dur_ms = 12.5
    record.code = "E_NONE"

    line = formatter.format(record)
    data = json.loads(line)

    assert "ts" in data
    assert data["lvl"] == "INFO"
    assert data["comp"] == "wire"
    assert data["evt"] == "frame_sent"
    assert data["sid"] == "sess-1001"
    assert data["mid"] == 42
    assert data["dur_ms"] == 12.5
    assert data["code"] == "E_NONE"


def test_structured_logger_emits_sanitized_jsonl():
    """Verify StructuredLogger writes masked JSONL output to stream.

    # req: LOG-01
    """
    stream = io.StringIO()
    setup_logging(log_level="DEBUG", stream=stream)

    slogger = get_logger("broker")
    raw_secret = "b4c8e7f9a123456789abcdef0123456789abcdef0123456789abcdef01234567"

    slogger.info(
        evt="client_handshake",
        message=f"Client authenticated with token={raw_secret}",
        sid="session-xyz",
        mid=1,
        dur_ms=5.2,
        code=None,
        details={"secret": raw_secret, "user": "alice"},
    )

    output = stream.getvalue().strip()
    assert len(output) > 0
    parsed = json.loads(output)

    assert parsed["comp"] == "broker"
    assert parsed["evt"] == "client_handshake"
    assert parsed["sid"] == "session-xyz"
    assert parsed["mid"] == 1
    assert parsed["dur_ms"] == 5.2

    # Verify secret is nowhere in the serialized JSON
    assert raw_secret not in output
    assert raw_secret not in str(parsed)
    assert parsed["details"]["secret"] == "[REDACTED]"
    assert parsed["details"]["user"] == "alice"


def test_structured_logger_error_and_exception_handling():
    """Verify error events and tracebacks are captured in JSONL.

    # req: LOG-01
    """
    stream = io.StringIO()
    setup_logging(log_level="DEBUG", stream=stream)
    slogger = get_logger("device")

    try:
        raise ValueError("Simulated script exception with secret=xyz123")
    except ValueError:
        slogger.exception(
            evt="unhandled_device_error",
            message="Script failed",
            code="E_FL",
        )

    output = stream.getvalue().strip()
    parsed = json.loads(output)

    assert parsed["comp"] == "device"
    assert parsed["evt"] == "unhandled_device_error"
    assert parsed["code"] == "E_FL"
    assert "exc" in parsed
    assert "xyz123" not in parsed["exc"]


def test_structured_logger_levels_and_file_output(tmp_path: Path):
    """Verify debug, warning, critical methods and file handler setup.

    # req: LOG-01
    """
    log_file = tmp_path / "test.log"
    setup_logging(log_level="DEBUG", log_file=log_file)
    logger = get_logger("core")

    logger.debug("debug_evt", "Debug details")
    logger.warning("warn_evt", "Warning details")
    logger.critical("crit_evt", "Critical details")

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    debug_data = json.loads(lines[0])
    assert debug_data["lvl"] == "DEBUG"
    assert debug_data["evt"] == "debug_evt"

    warn_data = json.loads(lines[1])
    assert warn_data["lvl"] == "WARNING"

    crit_data = json.loads(lines[2])
    assert crit_data["lvl"] == "CRITICAL"


def test_redacting_filter_with_args():
    """Verify RedactingFilter cleans args when passed as dict or tuple.

    # req: LOG-01
    """
    f = RedactingFilter()
    rec1 = logging.LogRecord("test", logging.INFO, "f.py", 1, "Msg %s", ("secret=token123",), None)
    f.filter(rec1)
    assert "token123" not in str(rec1.args)

    rec2 = logging.LogRecord("test", logging.INFO, "f.py", 1, "Msg %(secret)s", (), None)
    rec2.args = {"secret": "my_secret_token", "normal": "ok"}
    f.filter(rec2)
    assert rec2.args["secret"] == "[REDACTED]"
    assert rec2.args["normal"] == "ok"


def test_disabled_log_level_does_not_emit():
    """Verify messages below active level are ignored.

    # req: LOG-01
    """
    stream = io.StringIO()
    setup_logging(log_level="WARNING", stream=stream)
    logger = get_logger("quiet")

    logger.debug("ignore_me")
    logger.info("ignore_me_too")
    assert stream.getvalue() == ""
