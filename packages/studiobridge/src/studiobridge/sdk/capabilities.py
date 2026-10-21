"""Capability preflight checks, interceptors, and gating for StudioBridge SDK.

Implements rule [CAP-02]: operations that would fail due to missing or degraded prerequisites
MUST fail early on the client with UnavailableError carrying actionable alternatives.
"""

from __future__ import annotations

from typing import Any

from studiobridge.core.capabilities import (
    CAP_ACTUATE_KEYSTROKE,
    CAP_EXPERIMENTAL_PLAYLIST_PLACE,
    CAP_LIVE_MIXER_WRITE,
    CAP_LIVE_PIANOROLL_APPLY,
    CAP_LIVE_PLAYLIST_CLIP_PLACE,
    CAP_LIVE_PLUGIN_PARAM_WRITE,
    CAP_LIVE_PROJECT,
    CAP_LIVE_PROJECT_SAVE,
    CAP_LIVE_TRANSPORT_CONTROL,
    CAP_LIVE_UI,
    CAP_OFFLINE_FLP_READ,
    CAP_OFFLINE_FLP_WRITE,
    CAP_PORT_WMS_LOOPBACK,
    CAP_RENDER_CLI,
    CAP_SANDBOX_FILE_IO,
    Capability,
    CapabilityRegistry,
    CapabilityState,
)
from studiobridge.core.errors import (
    DegradedError,
    ExperimentalDisabledError,
    UnavailableError,
)

# Map high-level operation namespaces / prefixes to required capability ID
OP_CAPABILITY_MAP: dict[str, str] = {
    # Transport operations
    "transport.": CAP_LIVE_TRANSPORT_CONTROL,
    # Mixer operations
    "mixer.": CAP_LIVE_MIXER_WRITE,
    # Channel operations
    "channels.": "live.channels",
    # Pattern operations
    "patterns.": "live.patterns",
    # Plugin write operations
    "plugins.": CAP_LIVE_PLUGIN_PARAM_WRITE,
    # Piano roll / note application
    "notes.": CAP_LIVE_PIANOROLL_APPLY,
    "pianoroll.": CAP_LIVE_PIANOROLL_APPLY,
    # Project persistence / general
    "project.": CAP_LIVE_PROJECT_SAVE,
    "general.": "live.project",
    # UI operations
    "ui.": "live.ui",
    # Playlist arrangement
    "playlist.": CAP_LIVE_PLAYLIST_CLIP_PLACE,
    # Offline and render operations
    "flp.read": CAP_OFFLINE_FLP_READ,
    "flp.write": CAP_OFFLINE_FLP_WRITE,
    "render.": CAP_RENDER_CLI,
    "actuate.": CAP_ACTUATE_KEYSTROKE,
}

__all__ = [
    "CAP_ACTUATE_KEYSTROKE",
    "CAP_LIVE_MIXER_WRITE",
    "CAP_LIVE_PIANOROLL_APPLY",
    "CAP_EXPERIMENTAL_PLAYLIST_PLACE",
    "CAP_LIVE_PLAYLIST_CLIP_PLACE",
    "CAP_LIVE_PLUGIN_PARAM_WRITE",
    "CAP_LIVE_PROJECT",
    "CAP_LIVE_UI",
    "CAP_LIVE_PROJECT_SAVE",
    "CAP_LIVE_TRANSPORT_CONTROL",
    "CAP_OFFLINE_FLP_READ",
    "CAP_OFFLINE_FLP_WRITE",
    "CAP_PORT_WMS_LOOPBACK",
    "CAP_RENDER_CLI",
    "CAP_SANDBOX_FILE_IO",
    "OP_CAPABILITY_MAP",
    "check_operation_capability",
    "gate_capability",
    "get_capability_for_op",
]


def get_capability_for_op(op: str) -> str | None:
    """Resolve required capability ID for an operation name, or None if unmapped."""
    for prefix, cap_id in OP_CAPABILITY_MAP.items():
        if op.startswith(prefix):
            return cap_id
    return None


def gate_capability(
    caps: CapabilityRegistry | dict[str, Capability] | dict[str, Any],
    capability_id: str,
    *,
    allow_degraded: bool = False,
) -> Capability:
    """Enforce capability availability per [CAP-02].

    Evaluates capability prerequisites and operational state. If degraded (when
    allow_degraded=False) or unavailable, raises UnavailableError carrying the
    specific capability ID and suggested alternative before issuing network or IPC calls.
    """
    cap: Capability | None = None

    if isinstance(caps, CapabilityRegistry):
        cap = caps.evaluate(capability_id)
    elif isinstance(caps, dict):
        raw = caps.get(capability_id)
        if isinstance(raw, Capability):
            cap = raw
        elif isinstance(raw, dict):
            cap = Capability.from_dict(raw)
        else:
            cap = Capability(
                id=capability_id,
                state=CapabilityState.UNAVAILABLE,
                reason=f"Capability '{capability_id}' is not registered.",
            )
    else:
        cap = Capability(
            id=capability_id,
            state=CapabilityState.UNAVAILABLE,
            reason=f"Unknown capability source: {type(caps).__name__}",
        )

    if cap.is_experimental and (
        cap.state in {CapabilityState.DEGRADED, CapabilityState.UNAVAILABLE} or not cap.is_available
    ):
        remedy = (
            f"Try alternative capability: {', '.join(cap.alternatives)}"
            if cap.alternatives
            else "Enable experimental feature flag in fl.safety."
        )
        reason_str = cap.reason or "Feature disabled"
        raise ExperimentalDisabledError(
            message=f"Experimental capability '{capability_id}' is disabled: {reason_str}",
            code="E_EXPERIMENTAL",
            details={
                "capability": capability_id,
                "reason": cap.reason,
                "alternatives": cap.alternatives,
                "evidence": cap.evidence,
            },
            capability=capability_id,
            alternatives=cap.alternatives,
            remedy=remedy,
        )

    if cap.state == CapabilityState.UNAVAILABLE:
        remedy = (
            f"Try alternative capability: {', '.join(cap.alternatives)}"
            if cap.alternatives
            else "Satisfy required prerequisites or consult 'sbridge doctor'."
        )
        reason_msg = cap.reason or "Prerequisites not satisfied"
        raise UnavailableError(
            message=f"Capability '{capability_id}' is unavailable: {reason_msg}",
            code="E_UNAVAILABLE",
            details={
                "capability": capability_id,
                "reason": cap.reason,
                "alternatives": cap.alternatives,
                "evidence": cap.evidence,
            },
            capability=capability_id,
            alternatives=cap.alternatives,
            remedy=remedy,
        )

    if cap.state == CapabilityState.DEGRADED and not allow_degraded:
        remedy = (
            f"Try alternative capability: {', '.join(cap.alternatives)}"
            if cap.alternatives
            else "Resolve degradation cause or enable degraded mode."
        )
        degraded_msg = cap.reason or "Running with reduced functionality"
        raise DegradedError(
            message=f"Capability '{capability_id}' is degraded: {degraded_msg}",
            code="E_DEGRADED",
            details={
                "capability": capability_id,
                "reason": cap.reason,
                "alternatives": cap.alternatives,
                "evidence": cap.evidence,
            },
            capability=capability_id,
            alternatives=cap.alternatives,
            remedy=remedy,
        )

    return cap


def check_operation_capability(
    caps: CapabilityRegistry | dict[str, Capability] | dict[str, Any],
    op: str,
    *,
    allow_degraded: bool = False,
) -> None:
    """Preflight check for an operation; gates capability if operation requires one."""
    cap_id = get_capability_for_op(op)
    if cap_id is not None:
        gate_capability(caps, cap_id, allow_degraded=allow_degraded)
