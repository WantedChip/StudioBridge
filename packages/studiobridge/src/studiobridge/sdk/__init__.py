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
from studiobridge.sdk.playlist import (
    AsyncPlaylist,
    SyncPlaylist,
)
from studiobridge.sdk.plugins import (
    AsyncPlugins,
    SyncPlugins,
)
from studiobridge.sdk.project import (
    AsyncProject,
    SyncProject,
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
    PlaylistTrack,
    PluginInfo,
    PluginParam,
    ProjectInfo,
    Slot,
    Verified,
)
from studiobridge.sdk.ui import (
    AsyncUi,
    SyncUi,
)

__all__ = [
    "AsyncBatchContext",
    "AsyncChannels",
    "AsyncMixer",
    "AsyncPatterns",
    "AsyncPlaylist",
    "AsyncPlugins",
    "AsyncProject",
    "AsyncRawApi",
    "AsyncStudio",
    "AsyncTraceContext",
    "AsyncTransport",
    "AsyncUi",
    "BaseBatchContext",
    "BatchContext",
    "Change",
    "Channel",
    "MixerTrack",
    "Pattern",
    "PlaylistTrack",
    "PluginInfo",
    "PluginParam",
    "ProjectInfo",
    "Session",
    "Slot",
    "StatsAccumulator",
    "Status",
    "Studio",
    "SyncBatchContext",
    "SyncChannels",
    "SyncMixer",
    "SyncPatterns",
    "SyncPlaylist",
    "SyncPlugins",
    "SyncProject",
    "SyncRawApi",
    "SyncTraceContext",
    "SyncTransport",
    "SyncUi",
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
