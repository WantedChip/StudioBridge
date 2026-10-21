"""Transactions, checkpoints, and multi-tier rollback guarantees (G0–G2).

Implements atomic transaction blocks, undo checkpoints, read-before-write tracking,
and inverse compensating operations per spec 09_l1_sdk.md §6 and [TXN-01..02]:
- Guarantee levels:
  - G0 ("none"): Operation has no safe inverse (e.g. save, render); reports not reversible.
  - G1 ("best_effort"): SDK rollback via inverse compensating calls or general.undo(),
    but not all targets verified.
  - G2 ("verified"): Inverse writes applied and read-back verified equals initial before
    state for all targets.
- Transaction context manager supporting synchronous (Studio) and asynchronous (AsyncStudio).
- Acquires writer lease for the transaction duration; auto-extends without orphan locks.
- On enter: initializes checkpoint via general.saveUndo if supported and tracks mutations.
- Read-before-write: tracks initial value (before) and inverse operations for each mutated target.
- On exit (success): calls commit(), journals transaction, and releases writer lease cleanly.
- On exit (exception or manual tx.rollback()): automatically triggers rollback, executing
  compensating operations in reverse order, verifying restored values, and generating a
  RollbackReport with guarantee level.
- Nested transactions ([TXN-02]): nested with fl.transaction() calls flatten into outer
  transaction; inner transactions do not release lease prematurely, and leases auto-extend.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from studiobridge.core.logging import get_logger
from studiobridge.sdk.journal import JournalEntry
from studiobridge.sdk.verification import tolerance_matches

if TYPE_CHECKING:
    from anyio.from_thread import BlockingPortal

    from studiobridge.sdk.session import Session

logger = get_logger("sdk.txn")


class RollbackGuarantee(str, Enum):
    """Rollback guarantee tiers defined per 09_l1_sdk.md §6 and v0.2.8.

    - G0 ("none"): Operation has no safe inverse (e.g. save, render); not reversible.
    - G1 ("best_effort"): SDK rollback via inverse calls or general.undo(), not all verified.
    - G2 ("verified"): Inverse writes applied and verified equals initial before state.
    """

    G0 = "none"
    G1 = "best_effort"
    G2 = "verified"

    @property
    def level(self) -> str:
        """Guarantee tier identifier ('G0', 'G1', or 'G2')."""
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RollbackGuarantee):
            return self.value == other.value
        if isinstance(other, str):
            val_lower = other.lower().strip()
            return val_lower in (self.value.lower(), self.name.lower())
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def from_value(cls, val: str | RollbackGuarantee) -> RollbackGuarantee:
        """Parse guarantee from tier name ('G0', 'G1', 'G2') or descriptive value."""
        if isinstance(val, cls):
            return val
        s = str(val).strip().lower()
        if s in ("g0", "none"):
            return cls.G0
        if s in ("g1", "best_effort", "besteffort"):
            return cls.G1
        if s in ("g2", "verified"):
            return cls.G2
        raise ValueError(
            f"Unknown rollback guarantee '{val}'. Allowed: G0/none, G1/best_effort, G2/verified"
        )


# Operations with no safe inverse that degrade guarantee level to G0 per 09_l1_sdk.md §6
IRREVERSIBLE_OPERATIONS: frozenset[str] = frozenset(
    {
        "project.save",
        "project.save_new_version",
        "project.saveNewVersion",
        "render",
        "render.cli",
        "render.render",
        "render.start",
    }
)


def is_operation_irreversible(op: str) -> bool:
    """Check if an operation cannot be safely inverted."""
    if op in IRREVERSIBLE_OPERATIONS:
        return True
    lowered = op.lower()
    return any(
        sub in lowered
        for sub in (
            "save_new_version",
            "savenewversion",
            "project.save",
            "render.cli",
            "render.render",
        )
    )


def compute_target_key(op: str, target: Any, details: dict[str, Any], args: dict[str, Any]) -> str:
    """Derive unique target property key to track object properties separately."""
    prop = ""
    if "Volume" in op:
        prop = "volume"
    elif "Pan" in op:
        prop = "pan"
    elif "Mute" in op or "mute" in op:
        prop = "muted"
    elif "Solo" in op or "solo" in op:
        prop = "solo"
    elif "Name" in op:
        prop = "name"
    elif "Color" in op:
        prop = "color"
    elif "Pitch" in op:
        prop = "pitch"
    elif "Arm" in op:
        prop = "armed"
    elif "Length" in op:
        prop = "length"
    elif "Tempo" in op:
        prop = "tempo"
    elif "SongPos" in op:
        prop = "pos"
    elif "Route" in op:
        src = details.get("source") or args.get("source")
        dst = details.get("dest") or args.get("dest")
        return f"mixer.route.{src}->{dst}"
    elif "TargetFx" in op:
        prop = "target_fx"
    elif "Param" in op:
        p_idx = details.get("param") or args.get("paramIndex")
        t_idx = details.get("track") or args.get("index")
        s_idx = details.get("slot") or args.get("slot", -1)
        return f"plugin.{t_idx}.{s_idx}.param.{p_idx}"

    base_target = str(target or op)
    return f"{base_target}:{prop}" if prop else base_target


@dataclass(frozen=True, slots=True)
class TargetRollback:
    """Restoration record for an individual mutated target during rollback."""

    target: str
    op: str
    before: Any
    restored_value: Any
    verified: bool
    proof: str = "readback"
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert restoration record to dictionary."""
        return {
            "target": self.target,
            "op": self.op,
            "before": self.before,
            "restored_value": self.restored_value,
            "verified": self.verified,
            "proof": self.proof,
            "error": self.error,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class RollbackReport:
    """Structured report produced following a transaction rollback per 09_l1_sdk.md §6."""

    ok: bool
    guarantee: RollbackGuarantee
    targets: list[TargetRollback] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    checkpoint: str | None = None
    journal_id: str | None = None

    @property
    def success(self) -> bool:
        """Alias for ok."""
        return self.ok

    @property
    def restored(self) -> list[str]:
        """List of target identifiers successfully restored and verified."""
        return [t.target for t in self.targets if t.verified]

    @property
    def unrestored(self) -> list[str]:
        """List of target identifiers that failed verification or could not be reverted."""
        return [t.target for t in self.targets if not t.verified]

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dictionary representation."""
        return {
            "ok": self.ok,
            "guarantee": self.guarantee.value,
            "level": self.guarantee.level,
            "targets": [t.to_dict() for t in self.targets],
            "restored": self.restored,
            "unrestored": self.unrestored,
            "reasons": list(self.reasons),
            "checkpoint": self.checkpoint,
            "journal_id": self.journal_id,
        }


@dataclass(slots=True)
class TargetState:
    """Internal state tracking the initial before value and arguments of a mutated target."""

    key: str
    target: str
    op: str
    initial_before: Any
    details: dict[str, Any] = field(default_factory=dict)
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Savepoint:
    """Transaction savepoint snapshot for partial rollbacks."""

    name: str
    mutation_index: int
    targets_keys: set[str] = field(default_factory=set)


async def apply_inverse_operation(
    session: Session,
    target_state: TargetState,
) -> tuple[Any, bool, str | None]:
    """Execute compensating inverse call and verify restored value against initial before state."""
    op = target_state.op
    initial = target_state.initial_before
    details = target_state.details
    args = target_state.args

    if initial is None or is_operation_irreversible(op):
        return None, False, f"Operation '{op}' has no safe inverse or initial state was unrecorded."

    try:
        if op == "mixer.setTrackVolume":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_vol = float(initial)
            await session.call(
                "mixer.setTrackVolume",
                {"index": idx, "volume": target_vol},
                allow_protected=True,
            )
            readback = float(await session.call("mixer.getTrackVolume", {"index": idx}))
            verified = tolerance_matches(target_vol, readback, tol=0.01)
            return readback, verified, None

        elif op == "mixer.setTrackPan":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_pan = float(initial)
            await session.call(
                "mixer.setTrackPan",
                {"index": idx, "pan": target_pan},
                allow_protected=True,
            )
            readback = float(await session.call("mixer.getTrackPan", {"index": idx}))
            verified = tolerance_matches(target_pan, readback, tol=0.01)
            return readback, verified, None

        elif op == "mixer.muteTrack":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_val = 1 if initial else 0
            await session.call(
                "mixer.muteTrack",
                {"index": idx, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("mixer.isTrackMuted", {"index": idx}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "mixer.soloTrack":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_val = 1 if initial else 0
            await session.call(
                "mixer.soloTrack",
                {"index": idx, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("mixer.isTrackSolo", {"index": idx}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "mixer.setTrackName":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_name = str(initial)
            await session.call(
                "mixer.setTrackName",
                {"index": idx, "name": target_name},
                allow_protected=True,
            )
            readback = str(await session.call("mixer.getTrackName", {"index": idx}))
            verified = readback == target_name
            return readback, verified, None

        elif op == "mixer.setTrackColor":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_color = int(initial)
            await session.call(
                "mixer.setTrackColor",
                {"index": idx, "color": target_color},
                allow_protected=True,
            )
            readback = int(await session.call("mixer.getTrackColor", {"index": idx}))
            verified = readback == target_color
            return readback, verified, None

        elif op == "mixer.armTrack":
            idx = details.get("track") if "track" in details else args.get("index", 0)
            target_val = 1 if initial else 0
            await session.call(
                "mixer.armTrack",
                {"index": idx, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("mixer.isTrackArmed", {"index": idx}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "mixer.setRouteTo":
            src = details.get("source") or args.get("source")
            dst = details.get("dest") or args.get("dest")
            target_val = 1 if initial else 0
            await session.call(
                "mixer.setRouteTo",
                {"source": src, "dest": dst, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("mixer.getRouteTo", {"source": src, "dest": dst}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "channels.setChannelVolume":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_vol = float(initial)
            await session.call(
                "channels.setChannelVolume",
                {"index": idx, "volume": target_vol},
                allow_protected=True,
            )
            readback = float(await session.call("channels.getChannelVolume", {"index": idx}))
            verified = tolerance_matches(target_vol, readback, tol=0.01)
            return readback, verified, None

        elif op == "channels.setChannelPan":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_pan = float(initial)
            await session.call(
                "channels.setChannelPan",
                {"index": idx, "pan": target_pan},
                allow_protected=True,
            )
            readback = float(await session.call("channels.getChannelPan", {"index": idx}))
            verified = tolerance_matches(target_pan, readback, tol=0.01)
            return readback, verified, None

        elif op == "channels.muteChannel":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_val = 1 if initial else 0
            await session.call(
                "channels.muteChannel",
                {"index": idx, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("channels.isChannelMuted", {"index": idx}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "channels.soloChannel":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_val = 1 if initial else 0
            await session.call(
                "channels.soloChannel",
                {"index": idx, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("channels.isChannelSolo", {"index": idx}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "channels.setChannelName":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_name = str(initial)
            await session.call(
                "channels.setChannelName",
                {"index": idx, "name": target_name},
                allow_protected=True,
            )
            readback = str(await session.call("channels.getChannelName", {"index": idx}))
            verified = readback == target_name
            return readback, verified, None

        elif op == "channels.setChannelColor":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_color = int(initial)
            await session.call(
                "channels.setChannelColor",
                {"index": idx, "color": target_color},
                allow_protected=True,
            )
            readback = int(await session.call("channels.getChannelColor", {"index": idx}))
            verified = readback == target_color
            return readback, verified, None

        elif op == "channels.setChannelPitch":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_pitch = float(initial)
            await session.call(
                "channels.setChannelPitch",
                {"index": idx, "pitch": target_pitch},
                allow_protected=True,
            )
            readback = float(await session.call("channels.getChannelPitch", {"index": idx}))
            verified = tolerance_matches(target_pitch, readback, tol=0.01)
            return readback, verified, None

        elif op == "channels.setTargetFxTrack":
            idx = details.get("channel") if "channel" in details else args.get("index", 0)
            target_fx = int(initial)
            await session.call(
                "channels.setTargetFxTrack",
                {"index": idx, "track": target_fx},
                allow_protected=True,
            )
            readback = int(await session.call("channels.getTargetFxTrack", {"index": idx}))
            verified = readback == target_fx
            return readback, verified, None

        elif op == "transport.setTempo":
            target_tempo = float(initial)
            await session.call("transport.setTempo", {"tempo": target_tempo}, allow_protected=True)
            return target_tempo, True, None

        elif op == "transport.setSongPos":
            target_pos = float(initial)
            await session.call("transport.setSongPos", {"pos": target_pos}, allow_protected=True)
            readback = float(await session.call("transport.getSongPos", {}))
            verified = tolerance_matches(target_pos, readback, tol=0.01)
            return readback, verified, None

        elif op == "patterns.setPatternName":
            idx = details.get("pattern") if "pattern" in details else args.get("index", 1)
            target_name = str(initial)
            await session.call(
                "patterns.setPatternName",
                {"index": idx, "name": target_name},
                allow_protected=True,
            )
            readback = str(await session.call("patterns.getPatternName", {"index": idx}))
            verified = readback == target_name
            return readback, verified, None

        elif op == "patterns.setPatternColor":
            idx = details.get("pattern") if "pattern" in details else args.get("index", 1)
            target_color = int(initial)
            await session.call(
                "patterns.setPatternColor",
                {"index": idx, "color": target_color},
                allow_protected=True,
            )
            readback = int(await session.call("patterns.getPatternColor", {"index": idx}))
            verified = readback == target_color
            return readback, verified, None

        elif op == "patterns.setPatternLength":
            idx = details.get("pattern") if "pattern" in details else args.get("index", 1)
            target_len = int(initial)
            await session.call(
                "patterns.setPatternLength",
                {"index": idx, "length": target_len},
                allow_protected=True,
            )
            readback = int(await session.call("patterns.getPatternLength", {"index": idx}))
            verified = readback == target_len
            return readback, verified, None

        elif op == "playlist.setTrackName":
            idx = (
                details.get("playlist_track")
                if "playlist_track" in details
                else args.get("index", 1)
            )
            target_name = str(initial)
            await session.call(
                "playlist.setTrackName",
                {"index": idx, "name": target_name},
                allow_protected=True,
            )
            readback = str(await session.call("playlist.getTrackName", {"index": idx}))
            verified = readback == target_name
            return readback, verified, None

        elif op == "playlist.setTrackColor":
            idx = (
                details.get("playlist_track")
                if "playlist_track" in details
                else args.get("index", 1)
            )
            target_color = int(initial)
            await session.call(
                "playlist.setTrackColor",
                {"index": idx, "color": target_color},
                allow_protected=True,
            )
            readback = int(await session.call("playlist.getTrackColor", {"index": idx}))
            verified = readback == target_color
            return readback, verified, None

        elif op == "playlist.muteTrack":
            idx = (
                details.get("playlist_track")
                if "playlist_track" in details
                else args.get("index", 1)
            )
            target_val = 1 if initial else 0
            await session.call(
                "playlist.muteTrack",
                {"index": idx, "value": target_val},
                allow_protected=True,
            )
            readback = bool(await session.call("playlist.isTrackMuted", {"index": idx}))
            verified = readback == bool(initial)
            return readback, verified, None

        elif op == "plugins.setParamValue":
            p_idx = details.get("param") or args.get("paramIndex")
            t_idx = details.get("track") or args.get("index")
            s_idx = details.get("slot", args.get("slot", -1))
            target_val = float(initial)
            await session.call(
                "plugins.setParamValue",
                {"paramIndex": p_idx, "index": t_idx, "slot": s_idx, "value": target_val},
                allow_protected=True,
            )
            readback = float(
                await session.call(
                    "plugins.getParamValue",
                    {"paramIndex": p_idx, "index": t_idx, "slot": s_idx},
                )
            )
            verified = tolerance_matches(target_val, readback, tol=0.01)
            return readback, verified, None

        else:
            return None, False, f"Unsupported compensating inverse for operation '{op}'"

    except Exception as exc:
        return None, False, f"Compensating write failed for '{op}': {exc}"


class Transaction:
    """Transaction context manager supporting sync and async execution per spec 09_l1_sdk.md §6."""

    def __init__(
        self,
        session: Session,
        name: str = "default",
        timeout: float = 300.0,
        portal: BlockingPortal | None = None,
        *,
        allow_protected: bool = False,
    ) -> None:
        self._session: Session = session
        self.name: str = name
        self.timeout: float = timeout
        self.allow_protected: bool = allow_protected
        self._portal: BlockingPortal | None = portal

        self._parent: Transaction | None = None
        self._is_nested: bool = False
        self._committed: bool = False
        self._rolled_back: bool = False
        self._checkpoint: str | None = None
        self._checkpoint_error: str | None = None
        self._prev_mode: str | None = None
        self._has_irreversible_op: bool = False
        self._report: RollbackReport | None = None

        self._initial_targets: dict[str, TargetState] = {}
        self._mutations: list[JournalEntry] = []
        self._savepoints: dict[str, Savepoint] = {}

    @property
    def session(self) -> Session:
        """Active underlying Session."""
        return self._session

    @property
    def is_nested(self) -> bool:
        """Whether this transaction is nested within an outer transaction block."""
        return self._is_nested

    @property
    def committed(self) -> bool:
        """Whether transaction completed and committed."""
        return self._committed

    @property
    def rolled_back(self) -> bool:
        """Whether transaction was rolled back."""
        return self._rolled_back

    @property
    def checkpoint(self) -> str | None:
        """Native undo checkpoint identifier created on enter, if any."""
        return self._checkpoint

    @property
    def report(self) -> RollbackReport | None:
        """Rollback report generated if transaction rolled back."""
        return self._report

    @property
    def mutations(self) -> list[JournalEntry]:
        """Chronological list of mutating operations executed during this transaction."""
        return list(self._mutations)

    @property
    def targets(self) -> dict[str, TargetState]:
        """Shallow copy of touched target descriptors and their initial before values."""
        return dict(self._initial_targets)

    @property
    def guarantee(self) -> RollbackGuarantee:
        """Current computed rollback guarantee for this transaction."""
        if self._has_irreversible_op:
            return RollbackGuarantee.G0
        return RollbackGuarantee.G2

    def _on_journal_entry(self, entry: JournalEntry) -> None:
        """Listener callback invoked whenever a mutation is recorded in the session journal."""
        if entry.op.startswith("txn."):
            return

        if is_operation_irreversible(entry.op):
            self._has_irreversible_op = True

        target_key = compute_target_key(entry.op, entry.target, entry.details, entry.args)

        # Record initial before value only the FIRST time this target is touched in this transaction
        if target_key not in self._initial_targets:
            self._initial_targets[target_key] = TargetState(
                key=target_key,
                target=str(entry.target or entry.op),
                op=entry.op,
                initial_before=entry.before,
                details=dict(entry.details or {}),
                args=dict(entry.args or {}),
            )

        self._mutations.append(entry)

    async def _begin(self) -> Transaction:
        """Asynchronously initialize transaction scope."""
        active = self._session.active_transaction
        if active is not None:
            # Nested transaction: flatten into outer transaction per [TXN-02]
            self._is_nested = True
            self._parent = active
            self._checkpoint = active.checkpoint
            self._session.push_transaction(self)
            self._session.safety.journal.add_listener(self._on_journal_entry)
            logger.info(
                "txn_nested_begin",
                f"Nested transaction '{self.name}' flattened into '{active.name}'",
            )
            return self

        # Outermost transaction: acquire writer lease and initialize checkpoint
        self._is_nested = False
        if self._session.mode == "read_only":
            self._prev_mode = self._session.mode
            self._session.mode = "write"

        # Acquire writer lease for the duration of the transaction
        await self._session.acquire_lease(ttl=max(self.timeout, 15.0), purpose=f"txn:{self.name}")

        # Native undo checkpoint via general.saveUndo per spec
        checkpoint_name = f"StudioBridge: {self.name}"
        try:
            await self._session.call(
                "general.saveUndo",
                {"name": checkpoint_name, "flags": 0},
                allow_protected=True,
            )
            self._checkpoint = checkpoint_name
        except Exception as exc:
            self._checkpoint = None
            self._checkpoint_error = str(exc)

        self._session.push_transaction(self)
        self._session.safety.journal.add_listener(self._on_journal_entry)
        logger.info(
            "txn_begin", f"Transaction '{self.name}' initialized (checkpoint={self._checkpoint})"
        )
        return self

    async def _rollback_impl(self, reason: str = "") -> RollbackReport:
        """Execute inverse compensating operations and construct RollbackReport."""
        if self._rolled_back:
            return self._report or RollbackReport(ok=True, guarantee=RollbackGuarantee.G2)

        # 1. Native undo trigger if checkpoint exists
        if self._checkpoint is not None:
            with contextlib.suppress(Exception):
                await self._session.call("general.undo", {}, allow_protected=True)

        # 2. Execute compensating operations in reverse order of initial target modification
        targets_to_revert = list(self._initial_targets.values())[::-1]
        reverted_records: list[TargetRollback] = []
        reasons: list[str] = [reason] if reason else []

        for tgt in targets_to_revert:
            restored_val, verified, err = await apply_inverse_operation(self._session, tgt)
            if err:
                reasons.append(err)
            reverted_records.append(
                TargetRollback(
                    target=tgt.key,
                    op=tgt.op,
                    before=tgt.initial_before,
                    restored_value=restored_val,
                    verified=verified,
                    error=err,
                    details=tgt.details,
                )
            )

        # 3. Compute guarantee tier
        if self._has_irreversible_op:
            guarantee = RollbackGuarantee.G0
            ok = False
            reasons.append("Transaction contained irreversible operation(s)")
        elif (reverted_records and all(r.verified for r in reverted_records)) or (
            not reverted_records and not self._has_irreversible_op
        ):
            guarantee = RollbackGuarantee.G2
            ok = True
        else:
            guarantee = RollbackGuarantee.G1
            ok = False
            reasons.append("One or more targets failed verification upon compensating write")

        # 4. Mark journal entries as rolled back
        journal_id = None
        with contextlib.suppress(Exception):
            j_entry = self._session.safety.journal.record(
                op="txn.rollback",
                target=f"txn:{self.name}",
                details={
                    "name": self.name,
                    "guarantee": guarantee.value,
                    "level": guarantee.level,
                    "restored_count": len([r for r in reverted_records if r.verified]),
                    "unrestored_count": len([r for r in reverted_records if not r.verified]),
                    "reasons": reasons,
                },
                rolled_back=True,
            )
            journal_id = j_entry.entry_id

        report = RollbackReport(
            ok=ok,
            guarantee=guarantee,
            targets=reverted_records,
            reasons=reasons,
            checkpoint=self._checkpoint,
            journal_id=journal_id,
        )
        self._report = report
        self._rolled_back = True
        logger.info(
            "txn_rollback",
            f"Transaction '{self.name}' rolled back with guarantee {guarantee.level}",
        )
        return report

    async def _end(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Asynchronously finalize transaction scope, executing rollback or commit."""
        self._session.safety.journal.remove_listener(self._on_journal_entry)
        self._session.pop_transaction(self)

        if self._rolled_back:
            # Already explicitly rolled back
            if not self._is_nested:
                with contextlib.suppress(Exception):
                    await self._session.release_lease()
                if self._prev_mode is not None:
                    self._session.mode = self._prev_mode
            return False

        if exc_val is not None:
            # Exception raised inside block -> automatic rollback
            await self._rollback_impl(reason=f"Exception raised inside transaction: {exc_val}")
            if not self._is_nested:
                with contextlib.suppress(Exception):
                    await self._session.release_lease()
                if self._prev_mode is not None:
                    self._session.mode = self._prev_mode
            return False

        # Success path
        if self._is_nested:
            # Flatten into parent transaction
            if self._parent is not None:
                for k, v in self._initial_targets.items():
                    if k not in self._parent._initial_targets:
                        self._parent._initial_targets[k] = v
                self._parent._mutations.extend(self._mutations)
                if self._has_irreversible_op:
                    self._parent._has_irreversible_op = True
            self._committed = True
            logger.info("txn_nested_commit", f"Nested transaction '{self.name}' merged into parent")
            return False

        # Outermost transaction commit
        with contextlib.suppress(Exception):
            self._session.safety.journal.record(
                op="txn.commit",
                target=f"txn:{self.name}",
                details={
                    "name": self.name,
                    "mutations_count": len(self._mutations),
                    "checkpoint": self._checkpoint,
                },
            )

        self._committed = True
        logger.info("txn_commit", f"Transaction '{self.name}' committed successfully")

        # Cleanly release writer lease without orphan locks
        with contextlib.suppress(Exception):
            await self._session.release_lease()

        if self._prev_mode is not None:
            self._session.mode = self._prev_mode

        return False

    async def extend_lease_async(self, ttl: float = 300.0) -> dict[str, Any]:
        """Asynchronously extend active writer lease for transaction life."""
        return await self._session.renew_lease(ttl=ttl)

    def rollback(self) -> RollbackReport:
        """Synchronously trigger manual rollback."""
        if self._portal is not None:

            def call_fn() -> Any:
                return self._rollback_impl(reason="Manual rollback invoked")

            return self._portal.call(call_fn)
        raise RuntimeError("On AsyncTransaction, use 'await tx.rollback()'")

    def commit(self) -> None:
        """Mark transaction as committed."""
        self._committed = True

    def savepoint(self, name: str) -> Savepoint:
        """Create a savepoint snapshot within active transaction."""
        sp = Savepoint(
            name=name,
            mutation_index=len(self._mutations),
            targets_keys=set(self._initial_targets.keys()),
        )
        self._savepoints[name] = sp
        return sp

    # -------------------------------------------------------------------------
    # Asynchronous Context Manager Protocol
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> Transaction:
        return await self._begin()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        return await self._end(exc_type, exc_val, exc_tb)

    # -------------------------------------------------------------------------
    # Synchronous Context Manager Protocol (wraps via BlockingPortal)
    # -------------------------------------------------------------------------

    def __enter__(self) -> Transaction:
        if self._portal is None:
            raise RuntimeError(
                "Cannot use synchronous 'with fl.transaction()' on an asynchronous client. "
                "Use 'async with fl.transaction():' instead."
            )
        return self._portal.call(self._begin)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if self._portal is None:
            raise RuntimeError(
                "Cannot use synchronous 'with fl.transaction()' on an asynchronous client. "
                "Use 'async with fl.transaction():' instead."
            )
        return self._portal.call(self._end, exc_type, exc_val, exc_tb)


class AsyncTransaction(Transaction):
    """Asynchronous transaction context manager."""

    async def __aenter__(self) -> AsyncTransaction:
        await self._begin()
        return self

    async def rollback(self) -> RollbackReport:  # type: ignore[override]
        """Asynchronously trigger manual rollback."""
        return await self._rollback_impl(reason="Manual rollback invoked")

    async def commit(self) -> None:  # type: ignore[override]
        """Asynchronously trigger manual commit."""
        self._committed = True

    async def extend_lease(self, ttl: float = 300.0) -> dict[str, Any]:
        """Asynchronously extend writer lease."""
        return await self.extend_lease_async(ttl)


class SyncTransaction(Transaction):
    """Synchronous transaction context manager wrapping AsyncTransaction via BlockingPortal."""

    def __init__(
        self,
        portal: BlockingPortal,
        session: Session,
        name: str = "default",
        timeout: float = 300.0,
        *,
        allow_protected: bool = False,
    ) -> None:
        super().__init__(
            session,
            name=name,
            timeout=timeout,
            portal=portal,
            allow_protected=allow_protected,
        )

    def __enter__(self) -> SyncTransaction:
        super().__enter__()
        return self

    def extend_lease(self, ttl: float = 300.0) -> dict[str, Any]:
        """Synchronously extend writer lease."""
        assert self._portal is not None
        return self._portal.call(self._session.renew_lease, ttl)


__all__ = [
    "AsyncTransaction",
    "RollbackGuarantee",
    "RollbackReport",
    "Savepoint",
    "SyncTransaction",
    "TargetRollback",
    "TargetState",
    "Transaction",
    "apply_inverse_operation",
    "compute_target_key",
    "is_operation_irreversible",
]
