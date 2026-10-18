"""StudioBridge high-level Python SDK client."""

from __future__ import annotations

from studiobridge.sdk.batch import (
    AsyncBatchContext,
    BaseBatchContext,
    BatchContext,
    Change,
    SyncBatchContext,
    WriteReport,
    build_write_report,
)
from studiobridge.sdk.capabilities import (
    check_operation_capability,
    gate_capability,
    get_capability_for_op,
)
from studiobridge.sdk.client import (
    AsyncRawApi,
    AsyncStudio,
    Studio,
    SyncRawApi,
    connect,
)
from studiobridge.sdk.session import (
    Session,
    Status,
)
from studiobridge.sdk.trace import (
    AsyncTraceContext,
    StatsAccumulator,
    SyncTraceContext,
    TraceContext,
    TraceRecord,
    redact_secrets,
)

__all__ = [
    "AsyncBatchContext",
    "AsyncRawApi",
    "AsyncStudio",
    "AsyncTraceContext",
    "BaseBatchContext",
    "BatchContext",
    "Change",
    "Session",
    "StatsAccumulator",
    "Status",
    "Studio",
    "SyncBatchContext",
    "SyncRawApi",
    "SyncTraceContext",
    "TraceContext",
    "TraceRecord",
    "WriteReport",
    "build_write_report",
    "check_operation_capability",
    "connect",
    "gate_capability",
    "get_capability_for_op",
    "redact_secrets",
]
