"""Unit tests for StudioBridge Safety Modes, Protected Targets & Confirmation Gates."""

from __future__ import annotations

import pytest

from studiobridge.core.errors import (
    ConfirmationRequiredError,
    ProtectedTargetError,
    ReadOnlyError,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.client import Studio
from studiobridge.sdk.policy import Policy
from studiobridge.sdk.safety import SafetyManager


def test_safety_mode_normalization() -> None:
    """Verify safety mode normalization and validation."""
    mgr = SafetyManager(mode="read_only")
    assert mgr.mode == "read_only"
    assert mgr.is_read_only is True

    mgr.set_mode("write_with_confirm")
    assert mgr.mode == "write_with_confirm"
    assert mgr.is_read_only is False

    mgr.set_mode("write")
    assert mgr.mode == "write_autonomous"

    mgr.set_mode("unsafe")
    assert mgr.mode == "write_autonomous"

    with pytest.raises(ValueError) as exc:
        mgr.set_mode("invalid_mode")
    assert "Invalid safety mode" in str(exc.value)


def test_safety_check_read_only_rejection() -> None:
    """Verify read-only mode rejects mutating operations with ReadOnlyError (E_READONLY)."""
    mgr = SafetyManager(mode="read_only")

    # Read operations pass
    mgr.check_operation("mixer.getTrackVolume", {"index": 1})
    mgr.check_operation("transport.getTempo", {})

    # Mutating operation raises ReadOnlyError
    with pytest.raises(ReadOnlyError) as exc_info:
        mgr.check_operation("mixer.setTrackVolume", {"index": 1, "volume": 0.8})
    assert exc_info.value.code == "E_READONLY"


def test_safety_confirmation_gate() -> None:
    """Verify write_with_confirm mode requires confirmation token or callback."""
    mgr = SafetyManager(mode="write_with_confirm")

    # Mutation without confirmation raises ConfirmationRequiredError (E_CONFIRM)
    with pytest.raises(ConfirmationRequiredError) as exc_info:
        mgr.check_operation("mixer.setTrackVolume", {"index": 1, "volume": 0.8})
    assert exc_info.value.code == "E_CONFIRM"
    token = exc_info.value.token
    assert token is not None

    # Providing the generated confirmation token permits operation
    mgr.check_operation(
        "mixer.setTrackVolume",
        {"index": 1, "volume": 0.8},
        confirm_token=token,
    )

    # Token cannot be reused (consumed once)
    with pytest.raises(ConfirmationRequiredError):
        mgr.check_operation(
            "mixer.setTrackVolume",
            {"index": 1, "volume": 0.8},
            confirm_token=token,
        )

    # confirm=True override bypasses confirmation prompt
    mgr.check_operation(
        "mixer.setTrackVolume",
        {"index": 1, "volume": 0.8},
        confirm=True,
    )


def test_safety_confirmation_callback() -> None:
    """Verify confirmation callback handling in write_with_confirm."""
    mgr = SafetyManager(mode="write_with_confirm")

    # Approved callback
    mgr.on_confirmation(lambda op, args: True)
    mgr.check_operation("mixer.setTrackVolume", {"index": 1, "volume": 0.8})

    # Denied callback raises ConfirmationRequiredError
    mgr.on_confirmation(lambda op, args: False)
    with pytest.raises(ConfirmationRequiredError):
        mgr.check_operation("mixer.setTrackVolume", {"index": 1, "volume": 0.8})


def test_protected_target_master_track() -> None:
    """Verify Master mixer track (index 0) requires allow_protected=True [SAF-02]."""
    mgr = SafetyManager(mode="write_autonomous")

    # Non-master track (index 1) does not require allow_protected
    mgr.check_operation("mixer.setTrackVolume", {"index": 1, "volume": 0.8})

    # Master track (index 0) volume mutation raises ProtectedTargetError (E_PROTECTED)
    with pytest.raises(ProtectedTargetError) as exc_info:
        mgr.check_operation("mixer.setTrackVolume", {"index": 0, "volume": 0.8})
    assert exc_info.value.code == "E_PROTECTED"
    assert "Master mixer track" in str(exc_info.value)

    # Master track mute also protected
    with pytest.raises(ProtectedTargetError):
        mgr.check_operation("mixer.setTrackMute", {"index": 0, "mute": 1})

    # Passing allow_protected=True permits Master track modification
    mgr.check_operation(
        "mixer.setTrackVolume",
        {"index": 0, "volume": 0.8},
        allow_protected=True,
    )


def test_protected_target_tempo_and_custom() -> None:
    """Verify protected tempo when enabled by policy and custom protected targets."""
    policy = Policy(protect_tempo=True)
    mgr = SafetyManager(mode="write_autonomous", policy=policy)

    # Tempo is protected
    with pytest.raises(ProtectedTargetError) as exc_tempo:
        mgr.check_operation("transport.setTempo", {"bpm": 128.0})
    assert exc_tempo.value.code == "E_PROTECTED"

    # Bypass with allow_protected=True
    mgr.check_operation("transport.setTempo", {"bpm": 128.0}, allow_protected=True)

    # Register custom protected target
    mgr.add_protected_target("channels.renameChannel")
    with pytest.raises(ProtectedTargetError):
        mgr.check_operation("channels.renameChannel", {"index": 0, "name": "Lead"})

    # Unregister custom protected target
    mgr.remove_protected_target("channels.renameChannel")
    mgr.check_operation("channels.renameChannel", {"index": 0, "name": "Lead"})


def test_live_safety_modes_and_protected_targets(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Live integration test: fl.safety mode switching, confirmation, and protected target."""
    port_sdk, _ = running_emulator
    with Studio.connect(
        embedded=True,
        port=port_sdk,
        secret=sdk_secret,
        mode="write",
    ) as fl:
        # Check safety namespace attached
        assert fl.safety.mode == "write_autonomous"
        assert fl.safety.journal is not None

        # Track 1 mutation in write_autonomous succeeds
        v1 = fl.mixer.set_volume(1, 0.75)
        assert v1.verified is True

        # Master track 0 without allow_protected=True raises ProtectedTargetError
        with pytest.raises(ProtectedTargetError) as exc_prot:
            fl.mixer.set_volume(0, 0.8)
        assert exc_prot.value.code == "E_PROTECTED"

        # Master track 0 with allow_protected=True succeeds
        v0 = fl.mixer.set_volume(0, 0.8, allow_protected=True)
        assert v0.verified is True

        # Switch to write_with_confirm
        fl.safety.mode = "write_with_confirm"
        assert fl.safety.mode == "write_with_confirm"

        # Mutating without confirm=True raises ConfirmationRequiredError
        with pytest.raises(ConfirmationRequiredError) as exc_conf:
            fl.mixer.set_volume(1, 0.7)
        assert exc_conf.value.code == "E_CONFIRM"

        # Mutating with confirm=True succeeds
        v_conf = fl.mixer.set_volume(1, 0.7, confirm=True)
        assert v_conf.verified is True

        # Switch to read_only
        fl.safety.mode = "read_only"
        assert fl.safety.mode == "read_only"

        # Mutating raises ReadOnlyError
        with pytest.raises(ReadOnlyError) as exc_ro:
            fl.mixer.set_volume(1, 0.6)
        assert exc_ro.value.code == "E_READONLY"

        # Journal contains all executed mutations
        entries = fl.safety.journal.list()
        assert len(entries) >= 3
