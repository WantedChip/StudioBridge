"""Confirmation flow engine and challenge-token validation for StudioBridge MCP.

Implements human confirmation flows per spec 10_l2_interfaces.md §2.3 and [MCP-10]:
- Multi Round-Trip Request (MRTR) / elicitation payload for 2026-07-28 clients.
- One-time random challenge phrase with confirm_token fallback for older clients.
- Single-use challenge token generation and verification with TTL expiration.
- Protected target checking requiring both allow_protected=True and confirmation.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from studiobridge.core.errors import ProtectedTargetError

DEFAULT_CONFIRMATION_TTL_SECONDS: float = 300.0  # 5 minutes


class ConfirmationManager:
    """Manages human confirmation challenges, tokens, and protected target interlocks."""

    def __init__(self, default_ttl: float = DEFAULT_CONFIRMATION_TTL_SECONDS) -> None:
        self.default_ttl: float = default_ttl
        # Token string -> dict of challenge metadata
        self._pending_tokens: dict[str, dict[str, Any]] = {}
        # Session-wide confirmation state for protected targets
        self._session_protected_confirmed: bool = False
        self._session_write_confirmed: bool = False

    def generate_challenge_phrase(self, action: str = "write") -> str:
        """Generate a human-readable, one-time random challenge phrase.

        Format: confirm-{clean_action}-{hex4}
        """
        clean_action = action.replace(".", "-").replace("_", "-").lower()
        suffix = secrets.token_hex(3)
        return f"confirm-{clean_action}-{suffix}"

    def create_challenge(
        self,
        action: str,
        target: str = "",
        reason: str = "",
        client_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate and store a single-use confirmation challenge.

        Returns a structured dictionary adhering to the client's negotiated MCP version.
        """
        self._purge_expired()
        challenge_phrase = self.generate_challenge_phrase(action)
        token = challenge_phrase  # The phrase itself serves as the confirm_token
        expires_at = time.time() + self.default_ttl

        self._pending_tokens[token] = {
            "phrase": challenge_phrase,
            "action": action,
            "target": target,
            "reason": reason,
            "expires_at": expires_at,
            "created_at": time.time(),
            "details": details or {},
        }

        base_msg = (
            f"Confirmation required for action '{action}' on {target or 'FL Studio session'}."
        )
        if reason:
            base_msg += f" Reason: {reason}."
        prompt_msg = (
            f"{base_msg} Present challenge phrase '{challenge_phrase}' to the user "
            f"and re-call with confirm_token='{challenge_phrase}'."
        )

        res: dict[str, Any] = {
            "needs_confirmation": True,
            "challenge": challenge_phrase,
            "confirm_token": token,
            "action": action,
            "target": target,
            "message": prompt_msg,
            "expires_in_seconds": int(self.default_ttl),
        }

        # Multi Round-Trip Request (MRTR) / elicitation support for 2026-07-28 clients
        if client_version and client_version >= "2026-07-28":
            res["mrtr"] = True
            res["elicitation"] = {
                "type": "confirmation",
                "message": base_msg,
                "actions": ["approve", "reject"],
                "challenge": challenge_phrase,
            }

        return res

    def validate_token(self, token: str | None, expected_action: str | None = None) -> bool:
        """Validate and consume a single-use confirmation token.

        Single-use semantics: the token is purged immediately upon successful verification.
        """
        if not token or not isinstance(token, str):
            return False

        self._purge_expired()
        clean_token = token.strip()
        data = self._pending_tokens.get(clean_token)
        if data is None:
            return False

        # Verify action match if specified
        if expected_action is not None and data.get("action") != expected_action:
            # Action mismatch does not consume token
            return False

        # Valid: consume single-use token
        del self._pending_tokens[clean_token]
        return True

    def confirm_protected_session(self) -> None:
        """Record session-wide authorization for protected targets."""
        self._session_protected_confirmed = True

    def is_protected_session_confirmed(self) -> bool:
        """Check if protected operations were confirmed in the active session."""
        return self._session_protected_confirmed

    def confirm_write_session(self) -> None:
        """Record session-wide authorization for write operations."""
        self._session_write_confirmed = True

    def is_write_session_confirmed(self) -> bool:
        """Check if write mode was authorized."""
        return self._session_write_confirmed

    def reset(self) -> None:
        """Reset confirmation state and clear pending tokens."""
        self._pending_tokens.clear()
        self._session_protected_confirmed = False
        self._session_write_confirmed = False

    def _purge_expired(self) -> None:
        """Remove tokens whose TTL has lapsed."""
        now = time.time()
        expired = [tok for tok, meta in self._pending_tokens.items() if meta["expires_at"] < now]
        for tok in expired:
            del self._pending_tokens[tok]

    @staticmethod
    def is_protected_target(op: str, args: dict[str, Any] | None = None) -> tuple[bool, str]:
        """Check whether an operation targets a protected parameter per [SAF-02].

        Protected targets:
        1. Master mixer track (index 0) volume/mute/pan/solo/name/routing.
        2. Project tempo adjustment.
        3. Project file overwrite or destructive operations.
        4. Plugin replacement or removal.
        """
        call_args = args or {}

        # Master mixer track (index 0) volume/pan/mute/solo/name/routing
        if op == "mixer_set" or (
            op.startswith("mixer.")
            and any(
                op.split(".", 1)[1].startswith(p)
                for p in (
                    "setTrack",
                    "set_track",
                    "muteTrack",
                    "soloTrack",
                    "linkTrack",
                    "routeTrack",
                    "armTrack",
                    "set_volume",
                    "set_pan",
                    "set_mute",
                    "set_solo",
                    "set_name",
                )
            )
        ):
            idx = call_args.get("track", call_args.get("index"))
            if idx is not None:
                try:
                    if int(idx) == 0:
                        return True, "Master mixer track (index 0)"
                except (ValueError, TypeError):
                    pass
            # Check tracks array if passed
            tracks = call_args.get("tracks")
            if isinstance(tracks, list):
                for trk in tracks:
                    if isinstance(trk, dict) and trk.get("track") == 0:
                        return True, "Master mixer track (index 0)"

        # Project tempo
        if op in ("transport.setTempo", "transport.set_tempo", "transport_control"):
            action = call_args.get("action")
            tempo = call_args.get("tempo")
            if action == "tempo" or tempo is not None:
                return True, "Project tempo"

        # Project destructive save
        if op in ("project.save", "project.saveProject"):
            return True, "Project file overwrite"

        return False, ""

    def check_protected_target(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        allow_protected: bool = False,
        confirm_token: str | None = None,
        client_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Enforce [MCP-10] protected target interlocks.

        Requires BOTH allow_protected=True AND human confirmation in the same session.

        Raises:
            ProtectedTargetError: if allow_protected is False.

        Returns:
            Confirmation challenge dict if confirmation is needed, or None if authorized.
        """
        is_prot, desc = self.is_protected_target(op, args)
        if not is_prot:
            return None

        # 1. First gate: explicit allow_protected flag required
        if not allow_protected:
            raise ProtectedTargetError(
                f"Attempting to modify protected target: {desc} ([SAF-02], [MCP-10]). "
                f"Operation requires both allow_protected=True and confirmation.",
                code="E_PROTECTED",
                details={"operation": op, "target": desc, "args": args or {}},
                remedy=f"Re-run with allow_protected=True and confirm_token for {desc}.",
            )

        # 2. Second gate: confirmation required in the active session
        if self._session_protected_confirmed:
            return None

        if confirm_token and self.validate_token(confirm_token, expected_action=op):
            self.confirm_protected_session()
            return None

        # Generate challenge requesting confirmation
        return self.create_challenge(
            action=op,
            target=desc,
            reason=f"Modifying protected target '{desc}' requires human confirmation",
            client_version=client_version,
            details={"operation": op, "target": desc, "allow_protected": True},
        )

    def check_mode_and_confirmation(
        self,
        mode: str,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        confirm_token: str | None = None,
        client_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Check whether the active mode permits writes, or issue a confirmation challenge.

        If session is in 'read_only' mode:
        - If a valid confirm_token is provided, authorizes the write and switches to write mode.
        - Otherwise, returns a confirmation challenge prompting the user to switch mode.
        """
        if mode in ("write", "write_autonomous", "unsafe"):
            return None

        # Mode is read_only
        if confirm_token and self.validate_token(confirm_token, expected_action=op):
            self.confirm_write_session()
            return None

        # Also accept token for mode switch
        if confirm_token and self.validate_token(confirm_token, expected_action="studio_set_mode"):
            self.confirm_write_session()
            return None

        return self.create_challenge(
            action=op,
            target="session",
            reason=(
                f"Session is in '{mode}' mode. Mutating operation '{op}' "
                "requires 'write' mode and human confirmation"
            ),
            client_version=client_version,
            details={"operation": op, "mode": mode},
        )


__all__ = [
    "DEFAULT_CONFIRMATION_TTL_SECONDS",
    "ConfirmationManager",
]
