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
from studiobridge.sdk.channels import (
    AsyncChannels,
    SyncChannels,
)
from studiobridge.sdk.client import (
    AsyncRawApi,
    AsyncStudio,
    Studio,
    SyncRawApi,
    connect,
)
from studiobridge.sdk.mixer import (
    AsyncMixer,
    SyncMixer,
)
from studiobridge.sdk.patterns import (
    AsyncPatterns,
    SyncPatterns,
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
from studiobridge.sdk.transport import (
    AsyncTransport,
    SyncTransport,
)
from studiobridge.sdk.types import (
    Channel,
    MixerTrack,
    Pattern,
    Verified,
)

__all__ = [
    "AsyncBatchContext",
    "AsyncChannels",
    "AsyncMixer",
    "AsyncPatterns",
    "AsyncRawApi",
    "AsyncStudio",
    "AsyncTraceContext",
    "AsyncTransport",
    "BaseBatchContext",
    "BatchContext",
    "Change",
    "Channel",
    "MixerTrack",
    "Pattern",
    "Session",
    "StatsAccumulator",
    "Status",
    "Studio",
    "SyncBatchContext",
    "SyncChannels",
    "SyncMixer",
    "SyncPatterns",
    "SyncRawApi",
    "SyncTraceContext",
    "SyncTransport",
    "TraceContext",
    "TraceRecord",
    "Verified",
    "WriteReport",
    "build_write_report",
    "check_operation_capability",
    "connect",
    "gate_capability",
    "get_capability_for_op",
    "redact_secrets",
]
