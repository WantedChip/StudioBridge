"""Unit tests for capability preflight checks and capability gating.

Verifies [CAP-02], 09_l1_sdk.md §4, §10, and v0.2.3 Definition of Done:
- gate_capability() raising UnavailableError carrying capability ID and alternatives.
- fl.caps mapping protocol support.
- Operation prefix routing to capabilities.
- Preflight rejection of unallowlisted and unavailable calls.
"""

from __future__ import annotations

import pytest

from studiobridge.core.capabilities import (
    CAP_LIVE_MIXER_WRITE,
    CAP_LIVE_PIANOROLL_APPLY,
    CAP_LIVE_PLAYLIST_CLIP_PLACE,
    CAP_LIVE_PLUGIN_PARAM_WRITE,
    CAP_LIVE_PROJECT_SAVE,
    CAP_LIVE_TRANSPORT_CONTROL,
    CAP_OFFLINE_FLP_READ,
    Capability,
    CapabilityRegistry,
    CapabilityState,
    create_default_registry,
)
from studiobridge.core.errors import (
    DegradedError,
    ExperimentalDisabledError,
    UnavailableError,
)
from studiobridge.sdk.capabilities import (
    check_operation_capability,
    gate_capability,
    get_capability_for_op,
)
from studiobridge.sdk.client import Studio


def test_gate_capability_available() -> None:
    """gate_capability returns cleanly when capability is available and healthy."""
    registry = create_default_registry()
    cap = gate_capability(registry, CAP_OFFLINE_FLP_READ)
    assert cap.id == CAP_OFFLINE_FLP_READ
    assert cap.is_available is True
    assert cap.is_degraded is False


def test_gate_capability_unavailable() -> None:
    """gate_capability raises UnavailableError with ID, remedy, and alternatives."""
    registry = create_default_registry()
    registry.update(
        CAP_LIVE_PIANOROLL_APPLY,
        CapabilityState.UNAVAILABLE,
        reason="FL Studio score log oracle is not running on this host.",
        alternatives=[
            "Use offline FLP parsing/generation via Project.load()",
            "Generate MIDI file and import manually via File -> Import -> MIDI",
        ],
    )

    with pytest.raises(UnavailableError) as exc_info:
        gate_capability(registry, CAP_LIVE_PIANOROLL_APPLY)

    err = exc_info.value
    assert err.code == "E_UNAVAILABLE"
    assert err.capability_id == CAP_LIVE_PIANOROLL_APPLY
    assert "score log oracle" in err.message
    assert len(err.alternatives) == 2
    assert "Use offline FLP" in err.alternatives[0]
    assert err.remedy is not None


def test_gate_capability_degraded() -> None:
    """gate_capability raises DegradedError when allow_degraded=False."""
    registry = create_default_registry()
    registry.update(
        CAP_LIVE_MIXER_WRITE,
        CapabilityState.DEGRADED,
        reason="High MIDI latency (>50ms) causing slow read-back verification.",
        alternatives=["Use bulk batching to minimize round-trips"],
    )

    # By default allow_degraded=True, so it does not raise
    cap = gate_capability(registry, CAP_LIVE_MIXER_WRITE, allow_degraded=True)
    assert cap.is_degraded is True

    # When allow_degraded=False, it raises DegradedError
    with pytest.raises(DegradedError) as exc_info:
        gate_capability(registry, CAP_LIVE_MIXER_WRITE, allow_degraded=False)

    err = exc_info.value
    assert err.code == "E_DEGRADED"
    assert err.capability_id == CAP_LIVE_MIXER_WRITE
    assert "High MIDI latency" in err.message
    assert len(err.alternatives) == 1


def test_gate_capability_experimental_disabled() -> None:
    """gate_capability raises ExperimentalDisabledError when experimental feature is disabled."""
    registry = CapabilityRegistry()
    registry.register(
        Capability(
            id="experimental.playlist_place",
            name="Experimental Playlist Placement",
            state=CapabilityState.DEGRADED,
            is_experimental=True,
            reason="Feature flag experimental.playlist_place is disabled.",
            alternatives=["Enable via fl.safety.enable_experimental('playlist_place')"],
        )
    )

    with pytest.raises(ExperimentalDisabledError) as exc_info:
        gate_capability(registry, "experimental.playlist_place")

    err = exc_info.value
    assert err.code == "E_EXPERIMENTAL"
    assert err.capability_id == "experimental.playlist_place"
    assert len(err.alternatives) >= 1


def test_capability_registry_mapping_protocol() -> None:
    """Verify fl.caps supports mapping protocol (getitem, contains, iter, len)."""
    registry = create_default_registry()

    # __getitem__
    cap = registry[CAP_LIVE_MIXER_WRITE]
    assert cap.id == CAP_LIVE_MIXER_WRITE

    # __contains__
    assert CAP_LIVE_TRANSPORT_CONTROL in registry
    assert "nonexistent.capability" not in registry

    # __len__ and __iter__
    assert len(registry) >= 10
    keys = list(registry)
    assert CAP_LIVE_MIXER_WRITE in keys
    assert CAP_OFFLINE_FLP_READ in keys

    with pytest.raises(KeyError):
        _ = registry["unknown.cap"]


def test_get_capability_for_op() -> None:
    """Verify operation prefix routing to corresponding capability identifiers."""
    assert get_capability_for_op("mixer.getTrackVolume") == CAP_LIVE_MIXER_WRITE
    assert get_capability_for_op("mixer.setTrackVolume") == CAP_LIVE_MIXER_WRITE
    assert get_capability_for_op("channels.channelCount") == "live.channels"
    assert get_capability_for_op("transport.isPlaying") == CAP_LIVE_TRANSPORT_CONTROL
    assert get_capability_for_op("patterns.patternCount") == "live.patterns"
    assert get_capability_for_op("playlist.trackCount") == CAP_LIVE_PLAYLIST_CLIP_PLACE
    assert get_capability_for_op("plugins.getParamValue") == CAP_LIVE_PLUGIN_PARAM_WRITE
    assert get_capability_for_op("project.save") == CAP_LIVE_PROJECT_SAVE
    assert get_capability_for_op("general.getVersion") == "live.project"
    assert get_capability_for_op("ui.getFocused") == "live.ui"
    # Unmatched ops return None
    assert get_capability_for_op("unknown_custom_op") is None


def test_check_operation_capability() -> None:
    """check_operation_capability verifies mapped capability state before call execution."""
    registry = create_default_registry()

    # Allowed when available
    registry.update(CAP_LIVE_MIXER_WRITE, CapabilityState.AVAILABLE)
    check_operation_capability(registry, "mixer.getTrackVolume")

    # Rejected when registry marks capability unavailable
    registry.update(
        CAP_LIVE_MIXER_WRITE,
        CapabilityState.UNAVAILABLE,
        reason="Mixer subsystem disabled in test environment.",
        alternatives=["Route audio via master channel only."],
    )

    with pytest.raises(UnavailableError) as exc_info:
        check_operation_capability(registry, "mixer.getTrackVolume")

    err = exc_info.value
    assert err.capability_id == CAP_LIVE_MIXER_WRITE
    assert "Mixer subsystem disabled" in err.message
    assert "Route audio via master" in err.alternatives[0]


def test_client_raw_call_unallowlisted_rejection() -> None:
    """Calling unallowlisted operation raises UnavailableError carrying alternatives."""
    with Studio.connect(embedded=True) as fl:
        with pytest.raises(UnavailableError) as exc_info:
            fl.raw.call("os.system", "echo exploit")

        err = exc_info.value
        assert err.code == "E_UNAVAILABLE"
        assert "not in API allowlist" in err.message
        assert len(err.alternatives) >= 1
        assert err.remedy is not None


def test_client_raw_call_gated_by_capability() -> None:
    """Raw calls check capability registry and raise UnavailableError if unavailable."""
    with Studio.connect(embedded=True) as fl:
        fl.caps.update(
            CAP_LIVE_TRANSPORT_CONTROL,
            CapabilityState.UNAVAILABLE,
            reason="Transport control is locked during export.",
            alternatives=["Wait until audio export completes."],
        )

        with pytest.raises(UnavailableError) as exc_info:
            fl.raw.call("transport.isPlaying")

        err = exc_info.value
        assert err.code == "E_UNAVAILABLE"
        assert err.capability_id == CAP_LIVE_TRANSPORT_CONTROL
        assert "Transport control is locked" in err.message
