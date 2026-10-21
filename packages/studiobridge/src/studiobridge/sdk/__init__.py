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
from studiobridge.sdk.journal import (
    JournalEntry,
    MutationJournal,
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
from studiobridge.sdk.policy import (
    POLICY_FILE_NAMES,
    Policy,
)
from studiobridge.sdk.project import (
    AsyncProject,
    SyncProject,
)
from studiobridge.sdk.refs import (
    Channel,
    MixerTrack,
    Pattern,
    PlaylistTrack,
    Slot,
    resolve_reference,
)
from studiobridge.sdk.safety import (
    ALLOWED_SAFETY_MODES,
    AsyncSafetyManager,
    SafetyManager,
    SafetyMode,
    SyncSafetyManager,
    is_operation_mutating,
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
    PluginInfo,
    PluginParam,
    ProjectInfo,
    UntrustedString,
    Verified,
)
from studiobridge.sdk.ui import (
    AsyncUi,
    SyncUi,
)
from studiobridge.sdk.units import (
    DEFAULT_BEATS_PER_BAR,
    DEFAULT_PPQ,
    FL_PALETTE,
    RGB,
    Bars,
    Beats,
    Color,
    Db,
    Pan,
    Percent,
    Tempo,
    Ticks,
    Volume,
    from_ticks,
    to_ticks,
)
from studiobridge.sdk.verification import (
    DEFAULT_QUIRK_TOLERANCES,
    DEFAULT_TOLERANCE,
    ProofLevel,
    build_expect_guard,
    get_declared_tolerance,
    resolve_proof_level,
    tolerance_matches,
    verify_mutation,
)

__all__ = [
    "ALLOWED_SAFETY_MODES",
    "AsyncBatchContext",
    "AsyncChannels",
    "AsyncMixer",
    "AsyncPatterns",
    "AsyncPlaylist",
    "AsyncPlugins",
    "AsyncProject",
    "AsyncRawApi",
    "AsyncSafetyManager",
    "AsyncStudio",
    "AsyncTraceContext",
    "AsyncTransport",
    "AsyncUi",
    "Bars",
    "BaseBatchContext",
    "BatchContext",
    "Beats",
    "Change",
    "Channel",
    "Color",
    "DEFAULT_BEATS_PER_BAR",
    "DEFAULT_PPQ",
    "DEFAULT_QUIRK_TOLERANCES",
    "DEFAULT_TOLERANCE",
    "Db",
    "FL_PALETTE",
    "JournalEntry",
    "MixerTrack",
    "MutationJournal",
    "POLICY_FILE_NAMES",
    "Pan",
    "Pattern",
    "Percent",
    "PlaylistTrack",
    "PluginInfo",
    "PluginParam",
    "Policy",
    "ProjectInfo",
    "ProofLevel",
    "RGB",
    "SafetyManager",
    "SafetyMode",
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
    "SyncSafetyManager",
    "SyncTraceContext",
    "SyncTransport",
    "SyncUi",
    "Tempo",
    "Ticks",
    "TraceContext",
    "TraceRecord",
    "UntrustedString",
    "Verified",
    "Volume",
    "WriteReport",
    "build_expect_guard",
    "build_write_report",
    "check_operation_capability",
    "connect",
    "from_ticks",
    "gate_capability",
    "get_capability_for_op",
    "get_declared_tolerance",
    "is_operation_mutating",
    "redact_secrets",
    "resolve_proof_level",
    "resolve_reference",
    "to_ticks",
    "tolerance_matches",
    "verify_mutation",
]
