"""Mutation audit journal for StudioBridge SDK writes.

Implements append-only JSONL journal stored at
%LOCALAPPDATA%\\studiobridge\\journal\\{session_id}.jsonl recording
{ts, op, target, before, after, idem, user, proof, verified} per spec
09_l1_sdk.md §5, §6 and 12_crosscutting.md §1.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.core.paths import get_journal_dir


def _sanitize_session_id(session_id: str | int) -> str:
    """Sanitize session ID for safe filesystem filename."""
    s = str(session_id).strip()
    if not s or s == "0":
        s = "default"
    # Replace non-alphanumeric/dash/underscore with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", s)
    return sanitized or "default"


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """Single mutation audit journal record per 09_l1_sdk.md §6 and 12_crosscutting.md §1.

    Attributes:
        ts: Epoch timestamp of the write operation.
        op: Qualified operation name (e.g. 'mixer.setTrackVolume').
        target: Target identifier or reference (e.g. 'mixer.track.0').
        before: Target value before the mutation.
        after: Target value actually read back after the mutation.
        idem: Idempotency token or mutation sequence key.
        user: Client / user identifier performing the write.
        proof: Proof level ('readback', 'display_only', 'none').
        verified: True if post-write readback verified match.
        session_id: Session identifier string.
        args: Operation arguments dictionary.
        rolled_back: True if this mutation was rolled back by transaction engine.
        entry_id: Unique entry identifier.
        details: Extra context or evidence dictionary.
    """

    ts: float
    op: str
    target: Any = None
    before: Any = None
    after: Any = None
    idem: str = ""
    user: str = "sdk_user"
    proof: str = "readback"
    verified: bool = True
    session_id: str = "default"
    args: dict[str, Any] = field(default_factory=dict)
    rolled_back: bool = False
    entry_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return {
            "entry_id": self.entry_id,
            "ts": self.ts,
            "session_id": self.session_id,
            "op": self.op,
            "target": self.target,
            "args": self.args,
            "before": self.before,
            "after": self.after,
            "idem": self.idem,
            "user": self.user,
            "proof": self.proof,
            "verified": self.verified,
            "rolled_back": self.rolled_back,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JournalEntry:
        """Construct JournalEntry from dictionary."""
        return cls(
            entry_id=str(data.get("entry_id") or data.get("idem") or ""),
            ts=float(data.get("ts", time.time())),
            session_id=str(data.get("session_id", "default")),
            op=str(data.get("op", "")),
            target=data.get("target"),
            args=dict(data.get("args", {})),
            before=data.get("before"),
            after=data.get("after"),
            idem=str(data.get("idem", "")),
            user=str(data.get("user", "anonymous")),
            proof=str(data.get("proof", "none")),
            verified=bool(data.get("verified", False)),
            rolled_back=bool(data.get("rolled_back", False)),
            details=dict(data.get("details", {})),
        )


class MutationJournal:
    """Append-only mutation audit journal per session.

    Persists writes to disk in JSON Lines format:
    %LOCALAPPDATA%\\studiobridge\\journal\\{session_id}.jsonl
    """

    def __init__(
        self,
        session_id: str | int = "default",
        *,
        journal_dir: Path | None = None,
        log_path: Path | None = None,
        user: str | None = None,
    ) -> None:
        self._journal_dir: Path = journal_dir if journal_dir is not None else get_journal_dir()
        self._custom_log_path: Path | None = Path(log_path) if log_path is not None else None
        self._session_id: str = _sanitize_session_id(session_id)
        self.user: str = user or os.environ.get("USERNAME") or "sdk_user"
        self._entries: list[JournalEntry] = []
        self._ensure_dir()

    @property
    def session_id(self) -> str:
        """Active session identifier."""
        return self._session_id

    @session_id.setter
    def session_id(self, val: str | int) -> None:
        self._session_id = _sanitize_session_id(val)

    @property
    def path(self) -> Path:
        """Path to active session JSONL journal file."""
        if self._custom_log_path is not None:
            return self._custom_log_path
        return self._journal_dir / f"{self._session_id}.jsonl"

    def _ensure_dir(self) -> None:
        """Ensure parent journal directory exists."""
        with contextlib.suppress(Exception):
            if self._custom_log_path is not None:
                self._custom_log_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                self._journal_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        op: str,
        *,
        target: Any = None,
        args: dict[str, Any] | None = None,
        before: Any = None,
        after: Any = None,
        idem: str | None = None,
        user: str | None = None,
        proof: str = "readback",
        verified: bool = True,
        rolled_back: bool = False,
        entry_id: str | None = None,
        ts: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> JournalEntry:
        """Record a verified mutation to the session journal.

        Args:
            op: Operation name (e.g. 'mixer.setTrackVolume').
            target: Target descriptor (e.g. 'mixer.track.1').
            args: Operation arguments dictionary.
            before: Value before write.
            after: Value read back after write.
            idem: Idempotency token (generated if None).
            user: User ID override.
            proof: Proof level ('readback', 'display_only', 'none').
            verified: Read-back verification match status.
            rolled_back: Whether mutation was rolled back.
            entry_id: Optional unique entry id.
            ts: Optional timestamp override.
            details: Extra metadata or evidence dictionary.

        Returns:
            The recorded JournalEntry instance.
        """
        self._ensure_dir()
        t = round(ts if ts is not None else time.time(), 4)
        idem_token = idem or f"sb_{secrets.token_hex(6)}"
        ent_id = entry_id or idem_token
        user_id = user or self.user
        args_dict = dict(args or {})

        entry = JournalEntry(
            entry_id=ent_id,
            ts=t,
            session_id=self._session_id,
            op=op,
            target=target,
            args=args_dict,
            before=before,
            after=after,
            idem=idem_token,
            user=user_id,
            proof=proof,
            verified=verified,
            rolled_back=rolled_back,
            details=dict(details or {}),
        )

        # Append to in-memory list
        self._entries.append(entry)

        # Append-only write to JSONL file
        try:
            serialized = json.dumps(entry.to_dict())
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(serialized + "\n")
        except Exception:
            # Tolerant against ephemeral filesystem lock glitches while preserving in-memory
            pass

        return entry

    def list(
        self,
        *,
        op: str | None = None,
        target: Any = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[JournalEntry]:
        """List journal entries for active session with optional filtering.

        Args:
            op: Filter by operation name prefix or exact match.
            target: Filter by target identifier.
            since: Minimum epoch timestamp filter.
            limit: Return only the last N entries.

        Returns:
            List of matching JournalEntry objects.
        """
        entries = self._load_entries()
        results: list[JournalEntry] = []

        for entry in entries:
            if op is not None and not (entry.op == op or entry.op.startswith(op)):
                continue
            if target is not None and entry.target != target:
                continue
            if since is not None and entry.ts < since:
                continue
            results.append(entry)

        if limit is not None and limit > 0:
            return results[-limit:]
        return results

    def _load_entries(self) -> list[JournalEntry]:
        """Load entries from disk if file exists, syncing with in-memory list."""
        if not self.path.exists():
            return list(self._entries)

        try:
            entries: list[JournalEntry] = []
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        try:
                            data = json.loads(line_str)
                            entries.append(JournalEntry.from_dict(data))
                        except Exception:
                            continue
            return entries
        except Exception:
            return list(self._entries)

    def count(self) -> int:
        """Return total count of entries in the session journal."""
        return len(self._load_entries())

    def export(
        self,
        target_path: Path | str | None = None,
        *,
        format: str = "jsonl",
    ) -> str:
        """Export session journal entries.

        Args:
            target_path: Optional file path to write export into.
            format: 'jsonl' (default) or 'json'.

        Returns:
            String containing the serialized export.
        """
        entries = self._load_entries()
        if format.lower() == "json":
            content = json.dumps([e.to_dict() for e in entries], indent=2)
        else:
            content = "\n".join(json.dumps(e.to_dict()) for e in entries)
            if content:
                content += "\n"

        if target_path is not None:
            dest = Path(target_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        return content

    def clear(self) -> None:
        """Clear active session journal entries (in-memory and on-disk)."""
        self._entries.clear()
        if self.path.exists():
            with contextlib.suppress(Exception):
                self.path.unlink()


__all__ = [
    "JournalEntry",
    "MutationJournal",
]
