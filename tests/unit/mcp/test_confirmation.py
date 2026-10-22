"""Unit tests for ConfirmationManager and challenge-token verification per 10_l2_interfaces.md §2.3.

Verifies:
1. One-time challenge token generation, validation, and single-use consumption.
2. TTL expiration and automatic token purging.
3. Protocol-specific responses: MRTR / elicitation structure for 2026-07-28 clients,
   and standard challenge phrase for older clients.
4. Mode gating: read_only requires confirmation challenge; valid token switches mode.
5. Protected target gating [SAF-02, MCP-10]:
   - Requires both allow_protected=True AND confirmation in the session.
   - Raises ProtectedTargetError if allow_protected is missing.
   - Issues challenge if allow_protected=True but confirmation is missing.
   - Authorizes write when both allow_protected=True and confirm_token are supplied.
"""

from __future__ import annotations

import time

import pytest

from studiobridge.core.errors import ProtectedTargetError
from studiobridge.mcp.confirmation import ConfirmationManager


class TestConfirmationManagerTokens:
    """Verifies token generation, validation, and expiration lifecycle."""

    def test_challenge_phrase_format(self) -> None:
        """Challenge phrases are formatted as confirm-{action}-{hex}."""
        cm = ConfirmationManager()
        phrase = cm.generate_challenge_phrase("write")
        assert phrase.startswith("confirm-write-")
        assert len(phrase.split("-")) >= 3

        custom = cm.generate_challenge_phrase("mixer.setTrackVolume")
        assert custom.startswith("confirm-mixer-settrackvolume-")

    def test_single_use_token_validation(self) -> None:
        """Tokens are single-use: validated once then immediately purged."""
        cm = ConfirmationManager()
        challenge = cm.create_challenge(action="write_mode", target="session")
        token = challenge["confirm_token"]
        assert token is not None
        assert challenge["needs_confirmation"] is True
        assert challenge["challenge"] == token

        # First validation succeeds
        assert cm.validate_token(token, expected_action="write_mode") is True

        # Second validation fails (already consumed)
        assert cm.validate_token(token, expected_action="write_mode") is False

    def test_action_mismatch_does_not_consume(self) -> None:
        """Mismatched action leaves token intact for the correct action."""
        cm = ConfirmationManager()
        challenge = cm.create_challenge(action="studio_set_mode", target="mode:write")
        token = challenge["confirm_token"]

        # Action mismatch returns False
        assert cm.validate_token(token, expected_action="other_action") is False

        # Correct action still succeeds
        assert cm.validate_token(token, expected_action="studio_set_mode") is True

    def test_token_expiration(self) -> None:
        """Expired tokens cannot be validated."""
        cm = ConfirmationManager(default_ttl=0.01)  # 10ms TTL
        challenge = cm.create_challenge(action="quick_op")
        token = challenge["confirm_token"]

        time.sleep(0.02)
        assert cm.validate_token(token) is False


class TestConfirmationProtocolVersions:
    """Verifies MRTR / elicitation vs fallback payloads across MCP versions."""

    def test_2026_07_28_elicitation_payload(self) -> None:
        """2026-07-28 clients receive MRTR elicitation structure."""
        cm = ConfirmationManager()
        res = cm.create_challenge(
            action="studio_set_mode",
            target="mode:write",
            reason="Mutations requested",
            client_version="2026-07-28",
        )
        assert res["needs_confirmation"] is True
        assert res["mrtr"] is True
        assert "elicitation" in res
        el = res["elicitation"]
        assert el["type"] == "confirmation"
        assert "actions" in el
        assert "approve" in el["actions"]
        assert res["challenge"] is not None
        assert res["confirm_token"] is not None

    def test_older_client_fallback_payload(self) -> None:
        """Older clients (e.g. 2025-06-18) receive challenge phrase without MRTR."""
        cm = ConfirmationManager()
        res = cm.create_challenge(
            action="studio_set_mode",
            target="mode:write",
            reason="Mutations requested",
            client_version="2025-06-18",
        )
        assert res["needs_confirmation"] is True
        assert "mrtr" not in res
        assert "elicitation" not in res
        assert res["challenge"] is not None
        assert res["confirm_token"] is not None
        assert "confirm_token=" in res["message"]


class TestModeAndConfirmationGating:
    """Verifies mode checks and write authorization."""

    def test_read_only_mode_without_token_produces_challenge(self) -> None:
        """In read_only mode, mutating operation produces a challenge."""
        cm = ConfirmationManager()
        res = cm.check_mode_and_confirmation(mode="read_only", op="transport_control")
        assert res is not None
        assert res["needs_confirmation"] is True
        assert "challenge" in res

    def test_read_only_mode_with_valid_token_authorizes(self) -> None:
        """In read_only mode, providing valid confirm_token authorizes the write."""
        cm = ConfirmationManager()
        challenge = cm.create_challenge(action="transport_control")
        token = challenge["confirm_token"]

        res = cm.check_mode_and_confirmation(
            mode="read_only", op="transport_control", confirm_token=token
        )
        assert res is None  # None means authorized to proceed
        assert cm.is_write_session_confirmed() is True

    def test_write_mode_permits_immediately(self) -> None:
        """In write mode, no challenge is generated for standard mutations."""
        cm = ConfirmationManager()
        res = cm.check_mode_and_confirmation(mode="write", op="mixer_set")
        assert res is None


class TestProtectedTargetInterlocks:
    """Verifies [SAF-02, MCP-10] protected target enforcement."""

    def test_master_track_detected_as_protected(self) -> None:
        """Track 0 in mixer_set is recognized as protected."""
        is_prot, desc = ConfirmationManager.is_protected_target("mixer_set", {"track": 0})
        assert is_prot is True
        assert "Master mixer track" in desc

    def test_non_zero_track_not_protected(self) -> None:
        """Track 1 in mixer_set is not protected."""
        is_prot, _ = ConfirmationManager.is_protected_target("mixer_set", {"track": 1})
        assert is_prot is False

    def test_tempo_detected_as_protected(self) -> None:
        """Tempo adjustment in transport is recognized as protected."""
        is_prot, desc = ConfirmationManager.is_protected_target(
            "transport_control", {"action": "tempo", "tempo": 128.0}
        )
        assert is_prot is True
        assert "tempo" in desc.lower()

    def test_protected_target_without_allow_protected_raises(self) -> None:
        """Mutating protected target without allow_protected=True raises ProtectedTargetError."""
        cm = ConfirmationManager()
        with pytest.raises(ProtectedTargetError) as exc_info:
            cm.check_protected_target(
                "mixer_set",
                {"track": 0},
                allow_protected=False,
            )
        assert "E_PROTECTED" in str(exc_info.value.code)

    def test_protected_target_with_allow_protected_requires_confirmation(self) -> None:
        """With allow_protected=True but no confirmation, a challenge is issued."""
        cm = ConfirmationManager()
        challenge = cm.check_protected_target(
            "mixer_set",
            {"track": 0},
            allow_protected=True,
            confirm_token=None,
        )
        assert challenge is not None
        assert challenge["needs_confirmation"] is True
        assert "challenge" in challenge

    def test_protected_target_authorized_with_token(self) -> None:
        """Supplying both allow_protected=True and valid confirm_token authorizes write."""
        cm = ConfirmationManager()
        # Create challenge for the protected target
        challenge = cm.create_challenge(action="mixer_set", target="Master mixer track (index 0)")
        token = challenge["confirm_token"]

        res = cm.check_protected_target(
            "mixer_set",
            {"track": 0},
            allow_protected=True,
            confirm_token=token,
        )
        assert res is None  # Authorized
        assert cm.is_protected_session_confirmed() is True

        # Subsequent protected targets in the same session are also authorized
        subsequent = cm.check_protected_target(
            "mixer_set",
            {"track": 0},
            allow_protected=True,
        )
        assert subsequent is None
