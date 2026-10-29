"""Structured trace capture and in-process metrics accumulator for StudioBridge SDK.

Implements observability hooks:
- TraceContext capturing wire frames and timings to logs/trace-*.jsonl with secret redaction.
- fl.stats() runtime metrics accumulator.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from studiobridge.core.paths import get_app_data_dir

REDACT_KEYS = {"secret", "token", "password", "auth", "key", "access_token", "nonce"}
HEX_SECRET_PATTERN = re.compile(r"^[0-9a-fA-F]{32,64}$")


def redact_secrets(data: Any) -> Any:
    """Recursively redact secrets, tokens, and cryptographic keys from trace records."""
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for k, v in data.items():
            if any(target in k.lower() for target in REDACT_KEYS):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_secrets(v)
        return redacted
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(redact_secrets(item) for item in data)
    elif isinstance(data, str):
        if HEX_SECRET_PATTERN.match(data):
            return "[REDACTED]"
        return data
    elif isinstance(data, (bytes, bytearray)):
        return f"<bytes len={len(data)}>"
    return data


@dataclass(frozen=True, slots=True)
class TraceRecord:
    """Individual captured wire or operation trace event."""

    timestamp: float
    direction: str  # "send" | "recv" | "call"
    op: str
    duration_ms: float | None = None
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize TraceRecord with redacted data."""
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "op": self.op,
            "duration_ms": self.duration_ms,
            "data": redact_secrets(self.data),
            "error": self.error,
        }


class StatsAccumulator:
    """Thread-safe in-process metrics and telemetry accumulator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_calls: int = 0
        self._successful_calls: int = 0
        self._failed_calls: int = 0
        self._total_batches: int = 0
        self._total_pings: int = 0
        self._total_duration_ms: float = 0.0
        self._last_rtt_ms: float = 0.0
        self._bytes_sent: int = 0
        self._bytes_recv: int = 0

    def record_call(
        self,
        op: str,
        duration_ms: float,
        success: bool,
        bytes_sent: int = 0,
        bytes_recv: int = 0,
    ) -> None:
        """Record a single operation execution."""
        with self._lock:
            self._total_calls += 1
            if success:
                self._successful_calls += 1
            else:
                self._failed_calls += 1
            self._total_duration_ms += duration_ms
            self._bytes_sent += bytes_sent
            self._bytes_recv += bytes_recv

    def record_batch(self, count: int, duration_ms: float, success: bool) -> None:
        """Record a batch execution."""
        with self._lock:
            self._total_batches += 1
            self._total_calls += count
            if success:
                self._successful_calls += count
            else:
                self._failed_calls += count
            self._total_duration_ms += duration_ms

    def record_ping(self, rtt_ms: float) -> None:
        """Record round-trip ping time."""
        with self._lock:
            self._total_pings += 1
            self._last_rtt_ms = round(rtt_ms, 3)

    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time metrics snapshot."""
        with self._lock:
            avg_duration = (
                round(self._total_duration_ms / self._total_calls, 3)
                if self._total_calls > 0
                else 0.0
            )
            return {
                "calls": {
                    "total": self._total_calls,
                    "successful": self._successful_calls,
                    "failed": self._failed_calls,
                    "avg_duration_ms": avg_duration,
                },
                "batches": {
                    "total": self._total_batches,
                },
                "pings": {
                    "count": self._total_pings,
                    "last_rtt_ms": self._last_rtt_ms,
                },
                "total_calls": self._total_calls,
                "successful_calls": self._successful_calls,
                "failed_calls": self._failed_calls,
                "total_batches": self._total_batches,
                "total_duration_ms": round(self._total_duration_ms, 3),
                "avg_duration_ms": avg_duration,
                "last_rtt_ms": self._last_rtt_ms,
                "bytes_sent": self._bytes_sent,
                "bytes_recv": self._bytes_recv,
            }


class TraceContext:
    """Base trace collector managing event recording and file flushing."""

    def __init__(
        self,
        session: Any,
        output_path: Path | str | None = None,
    ) -> None:
        self._session = session
        self.output_path: Path | None = Path(output_path) if output_path else None
        self.events: list[TraceRecord] = []
        self.file_path: Path | None = None

    @property
    def records(self) -> list[TraceRecord]:
        """Return captured trace records."""
        return self.events

    def record(self, record: TraceRecord) -> None:
        """Add a trace record to this context."""
        self.events.append(record)

    def _resolve_file_path(self) -> Path:
        if self.output_path is not None:
            return self.output_path
        logs_dir = get_app_data_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        filename = f"trace-{int(time.time() * 1000)}.jsonl"
        return logs_dir / filename

    def flush(self) -> Path:
        """Flush captured trace events to JSONL file with secrets redacted."""
        path = self._resolve_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(event.to_dict()) + "\n")
        self.file_path = path
        return path


class AsyncTraceContext(TraceContext):
    """Asynchronous context manager capturing wire trace records."""

    async def __aenter__(self) -> AsyncTraceContext:
        if hasattr(self._session, "register_trace_collector"):
            self._session.register_trace_collector(self.record)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if hasattr(self._session, "unregister_trace_collector"):
            self._session.unregister_trace_collector(self.record)
        self.flush()


class SyncTraceContext(TraceContext):
    """Synchronous context manager capturing wire trace records."""

    def __init__(self, portal: Any, session: Any, output_path: Path | str | None = None) -> None:
        super().__init__(session, output_path)
        self._portal = portal

    def __enter__(self) -> SyncTraceContext:
        if hasattr(self._session, "register_trace_collector"):
            self._session.register_trace_collector(self.record)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if hasattr(self._session, "unregister_trace_collector"):
            self._session.unregister_trace_collector(self.record)
        self.flush()


__all__ = [
    "AsyncTraceContext",
    "HEX_SECRET_PATTERN",
    "REDACT_KEYS",
    "StatsAccumulator",
    "SyncTraceContext",
    "TraceContext",
    "TraceRecord",
    "redact_secrets",
]
