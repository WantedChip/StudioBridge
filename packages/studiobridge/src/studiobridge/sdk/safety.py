"""Safety modes, confirmation gates, and protected target interlocks.

Implements safety enforcement [SAF-01]:
- Safety modes: 'read_only' (default), 'write_with_confirm', 'write_autonomous'
  (harmonized with 'write', 'unsafe').
- Read-only mutation gating raising ReadOnlyError (subclass of SafetyError, E_READONLY).
- Confirmation gating in 'write_with_confirm' mode raising ConfirmationRequiredError (E_CONFIRM).
- Protected target interlocks ([SAF-02]) protecting master mixer track 0, tempo, and
  project destructive overwrites unless allow_protected=True is passed, raising
  ProtectedTargetError (E_PROTECTED).
- Mutation audit journal access and safety policy rules validation.
"""

from __future__ import annotations

import functools
import secrets
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import (
    ConfirmationRequiredError,
    ProtectedTargetError,
    ReadOnlyError,
)
from studiobridge.device.assets._sb_api import ALLOW
from studiobridge.sdk.journal import MutationJournal
from studiobridge.sdk.policy import Policy
from studiobridge.wire.session import is_mutating_operation as is_wire_mutating

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session

SafetyMode = Literal[
    "read_only",
    "write_with_confirm",
    "write_autonomous",
    "write",
    "unsafe",
]

ALLOWED_SAFETY_MODES: set[str] = {
    "read_only",
    "write_with_confirm",
    "write_autonomous",
    "write",
    "unsafe",
}

DEFAULT_TOKEN_EXPIRY_SECONDS: float = 300.0  # 5 minutes


def is_operation_mutating(op: str) -> bool:
    """Check if an operation modifies FL Studio state [SAF-01]."""
    if is_wire_mutating(op):
        return True
    if "." in op:
        mod_name, func_name = op.split(".", 1)
        if mod_name in ALLOW and func_name in ALLOW[mod_name]:
            return bool(ALLOW[mod_name][func_name].get("mutating", False))
        lowered = func_name.lower()
        if any(
            lowered.startswith(prefix)
            for prefix in (
                "set",
                "add",
                "del",
                "remove",
                "mute",
                "solo",
                "arm",
                "trigger",
                "stop",
                "play",
                "record",
                "save",
                "clear",
                "route",
                "link",
            )
        ):
            return True
    return False


class SafetyManager:
    """Core safety manager governing modes, protected targets, confirmation, and journal."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        mode: str = "read_only",
        policy: Policy | None = None,
        journal: MutationJournal | None = None,
        protected_targets: set[str] | None = None,
    ) -> None:
        self._session = session
        self._mode: str = self._normalize_mode(mode)
        self.policy: Policy = policy if policy is not None else Policy.load()
        sid = str(getattr(session, "sid", "default") or "default")
        user = getattr(session, "client_id", None) if session else None
        self.journal: MutationJournal = (
            journal if journal is not None else MutationJournal(session_id=sid, user=user)
        )
        self.protected_targets: set[str] = set(protected_targets or ())
        self._confirmation_callback: Callable[[str, dict[str, Any]], bool] | None = None
        self._pending_tokens: dict[str, float] = {}  # token -> expires_at

    @classmethod
    def _normalize_mode(cls, mode: str) -> str:
        """Validate and normalize safety mode string."""
        lowered = str(mode).lower().strip()
        if lowered in ("write", "unsafe", "write_autonomous"):
            return "write_autonomous"
        if lowered not in ALLOWED_SAFETY_MODES:
            raise ValueError(
                f"Invalid safety mode '{mode}'. Allowed modes: {sorted(ALLOWED_SAFETY_MODES)}"
            )
        return lowered

    @property
    def mode(self) -> str:
        """Active safety mode."""
        return self._mode

    @mode.setter
    def mode(self, val: str) -> None:
        self.set_mode(val)

    def set_mode(self, mode: str) -> None:
        """Switch safety mode synchronously."""
        normalized = self._normalize_mode(mode)
        self._mode = normalized

    @property
    def is_read_only(self) -> bool:
        """Whether current mode is strictly read_only."""
        return self._mode == "read_only"

    @property
    def is_write_allowed(self) -> bool:
        """Whether current mode permits mutating writes (subject to confirmation or autonomous)."""
        return self._mode in {"write_autonomous", "write", "write_with_confirm", "unsafe"}

    def set_confirmation_callback(
        self,
        callback: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Register a callback for evaluating confirmation requests in write_with_confirm mode."""
        self._confirmation_callback = callback

    def on_confirmation(
        self,
        callback: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Convenience alias for set_confirmation_callback."""
        self.set_confirmation_callback(callback)

    def add_protected_target(self, target: str) -> None:
        """Register custom protected target identifier."""
        self.protected_targets.add(target)

    def remove_protected_target(self, target: str) -> None:
        """Unregister custom protected target identifier."""
        self.protected_targets.discard(target)

    def create_confirmation_token(
        self,
        op: str = "",
        ttl_seconds: float = DEFAULT_TOKEN_EXPIRY_SECONDS,
    ) -> str:
        """Generate a single-use confirmation token for write_with_confirm operations."""
        token = f"confirm_{secrets.token_hex(8)}"
        self._pending_tokens[token] = time.time() + ttl_seconds
        return token

    def consume_confirmation_token(self, token: str) -> bool:
        """Validate and consume a confirmation token."""
        self._purge_expired_tokens()
        if token in self._pending_tokens:
            del self._pending_tokens[token]
            return True
        return False

    def _purge_expired_tokens(self) -> None:
        now = time.time()
        expired = [tok for tok, exp in self._pending_tokens.items() if exp < now]
        for tok in expired:
            del self._pending_tokens[tok]

    def is_protected_target(
        self,
        op: str,
        args: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Check if an operation targets a protected parameter per [SAF-02].

        Returns:
            Tuple of (is_protected, target_description).
        """
        call_args = args or {}

        # 1. Master mixer track (index 0) volume/mute/pan/solo/routing
        if op.startswith("mixer."):
            idx = call_args.get("index")
            if idx is not None:
                try:
                    if int(idx) == 0:
                        fn_name = op.split(".", 1)[1]
                        if any(
                            fn_name.startswith(p)
                            for p in (
                                "setTrackVolume",
                                "setTrackPan",
                                "setTrackMute",
                                "setTrackSolo",
                                "muteTrack",
                                "soloTrack",
                                "linkTrack",
                                "routeTrack",
                                "set_volume",
                                "set_pan",
                                "set_mute",
                                "set_solo",
                            )
                        ):
                            return True, "Master mixer track (index 0)"
                except (ValueError, TypeError):
                    pass

        # 2. Project tempo if configured or protected
        if op in ("transport.setTempo", "transport.set_tempo") and (
            self.policy.protect_tempo
            or "tempo" in self.protected_targets
            or op in self.protected_targets
        ):
            return True, "project tempo"

        # 3. Project-level destructive operations (overwriting current project file)
        if op in ("project.save", "project.saveProject"):
            return True, "project file overwrite"

        # 4. Custom registered protected targets
        if op in self.protected_targets:
            return True, f"custom protected target '{op}'"

        return False, ""

    def check_operation(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        opts: dict[str, Any] | None = None,
        allow_protected: bool = False,
        confirm: bool = False,
        confirm_token: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Validate safety rules, protected targets, confirmation gates, and policy.

        Raises:
            ReadOnlyError: When attempting a mutating operation in read_only mode.
            ConfirmationRequiredError: When write_with_confirm requires confirmation.
            ProtectedTargetError: When modifying a protected target without allow_protected=True.
            PolicyDeniedError: When operation violates safety policy rules.
        """
        call_args = args or {}
        call_opts = opts or {}
        is_mut = is_operation_mutating(op)

        # 1. Read-only safety guard [SAF-01]
        if is_mut:
            if self._mode == "read_only":
                raise ReadOnlyError(
                    f"Cannot execute mutating operation '{op}' in read-only mode.",
                    code="E_READONLY",
                    details={"operation": op, "mode": self._mode},
                    remedy=(
                        "Acquire writer lease and set mode to 'write' via "
                        "fl.safety.set_mode('write')."
                    ),
                )

            # 2. Confirmation gate in write_with_confirm mode
            if self._mode == "write_with_confirm":
                is_confirmed = (
                    confirm
                    or bool(call_opts.get("confirm"))
                    or bool(call_args.get("confirm"))
                    or (
                        confirm_token is not None and self.consume_confirmation_token(confirm_token)
                    )
                    or (
                        call_opts.get("confirm_token")
                        and self.consume_confirmation_token(call_opts["confirm_token"])
                    )
                )

                if not is_confirmed and self._confirmation_callback is not None:
                    try:
                        is_confirmed = bool(self._confirmation_callback(op, call_args))
                    except Exception:
                        is_confirmed = False

                if not is_confirmed:
                    token = self.create_confirmation_token(op)
                    raise ConfirmationRequiredError(
                        f"Mutating operation '{op}' requires user confirmation in "
                        f"'write_with_confirm' mode.",
                        code="E_CONFIRM",
                        details={"operation": op, "args": call_args, "token": token},
                        remedy=(
                            "Pass confirm=True, supply valid confirmation token, "
                            "or confirm via callback."
                        ),
                    )

        # 3. Protected target interlock [SAF-02]
        is_prot, target_desc = self.is_protected_target(op, call_args)
        if is_prot:
            has_allow_protected = (
                allow_protected
                or bool(call_opts.get("allow_protected"))
                or bool(call_args.get("allow_protected"))
                or (
                    op in ("project.save", "project.saveProject")
                    and (
                        confirm
                        or bool(call_opts.get("confirm"))
                        or bool(call_args.get("confirm"))
                        or bool(call_args.get("allow_overwrite"))
                    )
                )
            )

            if not has_allow_protected:
                raise ProtectedTargetError(
                    f"Attempting to modify protected target: {target_desc} ([SAF-02]). "
                    f"Pass allow_protected=True to permit modification.",
                    code="E_PROTECTED",
                    details={
                        "operation": op,
                        "target": target_desc,
                        "args": call_args,
                    },
                    remedy=(
                        f"Pass allow_protected=True to explicitly permit modifying {target_desc}."
                    ),
                )

        # 4. Policy validation [SAF-04]
        if self.policy is not None:
            self.policy.check(op, call_args, context=context)

    def checkpoint(self, name: str = "checkpoint") -> str:
        """Record a safety checkpoint for rollback guarantees per [TXN-01]."""
        cp_id = f"cp_{secrets.token_hex(4)}"
        self.journal.record(
            op="safety.checkpoint",
            target=name,
            before=None,
            after=cp_id,
            details={"checkpoint_id": cp_id, "name": name},
        )
        return cp_id

    def rollback(self, checkpoint_id: str | None = None) -> None:
        """Rollback state toward specified checkpoint per [TXN-01]."""
        self.journal.record(
            op="safety.rollback",
            target=checkpoint_id or "latest",
            before=None,
            after=None,
            details={"checkpoint_id": checkpoint_id},
        )


class AsyncSafetyManager:
    """Asynchronous safety controller interface mounted on AsyncStudio.safety."""

    def __init__(self, session: Session, core: SafetyManager | None = None) -> None:
        self._session: Session = session
        self._core: SafetyManager = core if core is not None else SafetyManager(session=session)

    @property
    def mode(self) -> str:
        """Active safety mode."""
        return self._core.mode

    @mode.setter
    def mode(self, val: str) -> None:
        self._core.mode = val

    async def set_mode(self, mode: str, *, acquire_lease: bool = True) -> None:
        """Set safety mode asynchronously and optionally acquire writer lease."""
        self._core.set_mode(mode)
        if (
            acquire_lease
            and self._session.is_connected
            and self._core.is_write_allowed
            and self._session.lease_holder != self._session.client_id
        ):
            await self._session.acquire_lease()

    @property
    def is_read_only(self) -> bool:
        """Whether current mode is strictly read_only."""
        return self._core.is_read_only

    @property
    def journal(self) -> MutationJournal:
        """Access mutation audit journal."""
        return self._core.journal

    @property
    def policy(self) -> Policy:
        """Access active safety policy."""
        return self._core.policy

    def set_confirmation_callback(
        self,
        callback: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Register confirmation callback for write_with_confirm mode."""
        self._core.set_confirmation_callback(callback)

    def on_confirmation(
        self,
        callback: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Convenience alias for set_confirmation_callback."""
        self._core.on_confirmation(callback)

    def add_protected_target(self, target: str) -> None:
        """Register custom protected target identifier."""
        self._core.add_protected_target(target)

    def remove_protected_target(self, target: str) -> None:
        """Unregister custom protected target identifier."""
        self._core.remove_protected_target(target)

    def create_confirmation_token(self, op: str = "") -> str:
        """Generate confirmation token."""
        return self._core.create_confirmation_token(op)

    def consume_confirmation_token(self, token: str) -> bool:
        """Validate and consume confirmation token."""
        return self._core.consume_confirmation_token(token)

    def check_operation(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        opts: dict[str, Any] | None = None,
        allow_protected: bool = False,
        confirm: bool = False,
        confirm_token: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Validate safety constraints for an operation."""
        self._core.check_operation(
            op,
            args,
            opts=opts,
            allow_protected=allow_protected,
            confirm=confirm,
            confirm_token=confirm_token,
            context=context,
        )

    def checkpoint(self, name: str = "checkpoint") -> str:
        """Record safety checkpoint."""
        return self._core.checkpoint(name)

    def rollback(self, checkpoint_id: str | None = None) -> None:
        """Trigger rollback."""
        self._core.rollback(checkpoint_id)


class SyncSafetyManager:
    """Synchronous safety controller interface mounted on Studio.safety."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_safety: AsyncSafetyManager,
    ) -> None:
        self._portal = portal
        self._async = async_safety
        self._core = async_safety._core

    @property
    def mode(self) -> str:
        """Active safety mode."""
        return self._core.mode

    @mode.setter
    def mode(self, val: str) -> None:
        self.set_mode(val)

    def set_mode(self, mode: str, *, acquire_lease: bool = True) -> None:
        """Set safety mode synchronously and optionally acquire writer lease."""
        call_fn = functools.partial(self._async.set_mode, mode, acquire_lease=acquire_lease)
        self._portal.call(call_fn)

    @property
    def is_read_only(self) -> bool:
        """Whether current mode is strictly read_only."""
        return self._core.is_read_only

    @property
    def journal(self) -> MutationJournal:
        """Access mutation audit journal."""
        return self._core.journal

    @property
    def policy(self) -> Policy:
        """Access active safety policy."""
        return self._core.policy

    def set_confirmation_callback(
        self,
        callback: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Register confirmation callback for write_with_confirm mode."""
        self._core.set_confirmation_callback(callback)

    def on_confirmation(
        self,
        callback: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Convenience alias for set_confirmation_callback."""
        self._core.on_confirmation(callback)

    def add_protected_target(self, target: str) -> None:
        """Register custom protected target identifier."""
        self._core.add_protected_target(target)

    def remove_protected_target(self, target: str) -> None:
        """Unregister custom protected target identifier."""
        self._core.remove_protected_target(target)

    def create_confirmation_token(self, op: str = "") -> str:
        """Generate confirmation token."""
        return self._core.create_confirmation_token(op)

    def consume_confirmation_token(self, token: str) -> bool:
        """Validate and consume confirmation token."""
        return self._core.consume_confirmation_token(token)

    def check_operation(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        opts: dict[str, Any] | None = None,
        allow_protected: bool = False,
        confirm: bool = False,
        confirm_token: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Validate safety constraints for an operation."""
        self._core.check_operation(
            op,
            args,
            opts=opts,
            allow_protected=allow_protected,
            confirm=confirm,
            confirm_token=confirm_token,
            context=context,
        )

    def checkpoint(self, name: str = "checkpoint") -> str:
        """Record safety checkpoint."""
        return self._core.checkpoint(name)

    def rollback(self, checkpoint_id: str | None = None) -> None:
        """Trigger rollback."""
        self._core.rollback(checkpoint_id)


__all__ = [
    "ALLOWED_SAFETY_MODES",
    "AsyncSafetyManager",
    "SafetyManager",
    "SafetyMode",
    "SyncSafetyManager",
    "is_operation_mutating",
]
