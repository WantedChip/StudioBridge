"""Structured JSONL logging with automated secret and token redaction.

Emits structured logs with standardized schema:
{ts, lvl, comp, evt, sid, mid, dur_ms, code}
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

# Sensitive key names to redact in dictionary payloads
SENSITIVE_KEY_NAMES: frozenset[str] = frozenset(
    {
        "secret",
        "token",
        "broker_token",
        "wire_secret",
        "auth",
        "authorization",
        "password",
        "api_key",
        "key",
        "private_key",
    }
)

# Patterns matching hex tokens, bearer authorization, or sensitive key=value strings
HEX_SECRET_PATTERN = re.compile(r"\b[0-9a-fA-F]{32,64}\b")
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]+")
KV_SECRET_PATTERN = re.compile(
    r"(?i)\b(secret|token|broker_token|password|api_key|auth|key)\s*[:=]\s*['\"]?([^\s,'\"]+)['\"]?"
)
USER_PATH_PATTERN = re.compile(
    r"(?i)([a-zA-Z]:[\\/]+Users[\\/]+)"
    r"(?!(?:\[REDACTED\]|public|default|all users)\b)"
    r"([^\\/\s\"',;:()\[\]]+)"
)
POSIX_USER_PATH_PATTERN = re.compile(
    r"(/(?:Users|home)/)"
    r"(?!(?:\[REDACTED\]|shared|default)\b)"
    r"([^/\\\s\"',;:()\[\]]+)"
)

REDACTED_STR = "[REDACTED]"


def redact_string(val: str) -> str:
    """Mask credentials, 256-bit hex tokens, private user paths, and secrets inside a string."""
    val = KV_SECRET_PATTERN.sub(r"\1=" + REDACTED_STR, val)
    val = BEARER_PATTERN.sub("Bearer " + REDACTED_STR, val)
    val = HEX_SECRET_PATTERN.sub(REDACTED_STR, val)
    val = USER_PATH_PATTERN.sub(r"\1" + REDACTED_STR, val)
    val = POSIX_USER_PATH_PATTERN.sub(r"\1" + REDACTED_STR, val)
    return val


def redact_sensitive_data(obj: Any) -> Any:
    """Recursively redact sensitive tokens and keys from dictionaries, lists, and strings."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for k, v in obj.items():
            k_str = str(k).lower()
            if any(sensitive in k_str for sensitive in SENSITIVE_KEY_NAMES):
                cleaned[k] = REDACTED_STR
            else:
                cleaned[k] = redact_sensitive_data(v)
        return cleaned

    if isinstance(obj, (list, tuple, set)):
        items = [redact_sensitive_data(item) for item in obj]
        return type(obj)(items) if not isinstance(obj, set) else set(items)

    if isinstance(obj, str):
        return redact_string(obj)

    return obj


class RedactingFilter(logging.Filter):
    """Filter that sanitizes secrets from log messages and attributes before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_string(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_sensitive_data(record.args)
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(redact_sensitive_data(a) for a in record.args)

        for attr in ("evt", "sid", "code", "details"):
            if hasattr(record, attr):
                setattr(record, attr, redact_sensitive_data(getattr(record, attr)))

        return True


class JsonlFormatter(logging.Formatter):
    """Formats log records as single-line JSONL adhering to StudioBridge log schema."""

    def format(self, record: logging.LogRecord) -> str:
        # Generate ISO 8601 UTC timestamp
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        # Format message safely
        try:
            formatted_msg = record.getMessage()
        except Exception:
            formatted_msg = str(record.msg)

        comp = getattr(record, "comp", None) or record.name
        evt = getattr(record, "evt", None) or "log"
        sid = getattr(record, "sid", None)
        mid = getattr(record, "mid", None)
        dur_ms = getattr(record, "dur_ms", None)
        code = getattr(record, "code", None)

        payload: dict[str, Any] = {
            "ts": ts,
            "lvl": record.levelname,
            "comp": comp,
            "evt": evt,
            "sid": sid,
            "mid": mid,
            "dur_ms": dur_ms,
            "code": code,
        }

        if formatted_msg and formatted_msg != evt:
            payload["msg"] = formatted_msg

        # Include optional contextual attributes
        for extra_key in ("idem", "plane", "details"):
            if hasattr(record, extra_key):
                val = getattr(record, extra_key)
                if val is not None:
                    payload[extra_key] = val

        # Handle exception tracebacks if present
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # Final sanitization pass
        sanitized = redact_sensitive_data(payload)
        return json.dumps(sanitized, ensure_ascii=False, default=str)


class StructuredLogger:
    """Component-scoped structured logger emitting standard JSONL records."""

    def __init__(self, comp: str, logger: logging.Logger) -> None:
        self.comp = comp
        self.logger = logger

    def log(
        self,
        level: int,
        evt: str,
        message: str | None = None,
        *,
        sid: str | None = None,
        mid: int | None = None,
        dur_ms: float | None = None,
        code: str | None = None,
        exc_info: bool = False,
        **extra: Any,
    ) -> None:
        """Emit a structured event with the standard fields."""
        if not self.logger.isEnabledFor(level):
            return

        log_extra = {
            "comp": self.comp,
            "evt": evt,
            "sid": sid,
            "mid": mid,
            "dur_ms": dur_ms,
            "code": code,
            **extra,
        }
        msg = message or evt
        self.logger.log(level, msg, extra=log_extra, exc_info=exc_info)

    def debug(self, evt: str, message: str | None = None, **kwargs: Any) -> None:
        self.log(logging.DEBUG, evt, message, **kwargs)

    def info(self, evt: str, message: str | None = None, **kwargs: Any) -> None:
        self.log(logging.INFO, evt, message, **kwargs)

    def warning(self, evt: str, message: str | None = None, **kwargs: Any) -> None:
        self.log(logging.WARNING, evt, message, **kwargs)

    def error(self, evt: str, message: str | None = None, **kwargs: Any) -> None:
        self.log(logging.ERROR, evt, message, **kwargs)

    def critical(self, evt: str, message: str | None = None, **kwargs: Any) -> None:
        self.log(logging.CRITICAL, evt, message, **kwargs)

    def exception(self, evt: str, message: str | None = None, **kwargs: Any) -> None:
        self.log(logging.ERROR, evt, message, exc_info=True, **kwargs)


def get_logger(comp: str) -> StructuredLogger:
    """Return a StructuredLogger instance bound to the specified component."""
    base_logger = logging.getLogger(f"studiobridge.{comp}")
    return StructuredLogger(comp=comp, logger=base_logger)


def setup_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    stream: TextIO | None = None,
) -> None:
    """Configure StudioBridge logging handlers with JSONL formatting and redaction."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger("studiobridge")
    root.setLevel(level)

    # Clear existing handlers
    root.handlers.clear()

    formatter = JsonlFormatter()
    redaction_filter = RedactingFilter()

    # Stream handler (stdout or custom stream)
    target_stream = stream or sys.stdout
    stream_handler = logging.StreamHandler(target_stream)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(redaction_filter)
    root.addHandler(stream_handler)

    # File handler if requested
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redaction_filter)
        root.addHandler(file_handler)
