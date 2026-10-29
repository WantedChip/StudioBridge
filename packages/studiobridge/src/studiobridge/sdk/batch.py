"""Batch call accumulator and WriteReport builder for StudioBridge SDK.

Implements batch execution.
Collects operations into a single wire batch request (`device.batch`) and returns a WriteReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T", bound="BaseBatchContext")


@dataclass(frozen=True, slots=True)
class Change:
    """Record of an individual state mutation or operation in a batch."""

    target: str
    before: Any = None
    after: Any = None
    verified: bool = True
    proof: str = "readback"  # "readback", "display_only", "none"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize Change to dictionary representation."""
        return {
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "verified": self.verified,
            "proof": self.proof,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class WriteReport:
    """Consolidated summary of verified changes and warnings resulting from a write or batch."""

    ok: bool
    changes: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    journal_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize WriteReport to dictionary representation."""
        return {
            "ok": self.ok,
            "changes": [c.to_dict() for c in self.changes],
            "warnings": list(self.warnings),
            "journal_id": self.journal_id,
        }


def build_write_report(
    results: list[Any],
    ops: list[dict[str, Any]],
    journal_id: str | None = None,
) -> WriteReport:
    """Construct a WriteReport by correlating operations with execution results."""
    changes: list[Change] = []
    warnings: list[str] = []

    for idx, op in enumerate(ops):
        target = op.get("op", f"op_{idx}")
        op_args = op.get("args", {})

        if idx >= len(results):
            warnings.append(f"Operation '{target}' did not receive a response from device")
            changes.append(
                Change(
                    target=target,
                    before=None,
                    after=None,
                    verified=False,
                    proof="none",
                    error="No response returned",
                )
            )
            continue

        res = results[idx]

        if isinstance(res, Exception):
            warnings.append(f"Operation '{target}' raised exception: {res}")
            changes.append(
                Change(
                    target=target,
                    before=None,
                    after=None,
                    verified=False,
                    proof="none",
                    error=str(res),
                )
            )
        elif isinstance(res, dict) and (res.get("ok") is False or "err" in res or "error" in res):
            err_msg = res.get("err") or res.get("error") or "Operation failed"
            warnings.append(f"Operation '{target}' failed: {err_msg}")
            changes.append(
                Change(
                    target=target,
                    before=None,
                    after=None,
                    verified=False,
                    proof="none",
                    error=str(err_msg),
                )
            )
        elif isinstance(res, dict) and "verified" in res:
            changes.append(
                Change(
                    target=res.get("target", target),
                    before=res.get("before"),
                    after=res.get("after", res.get("value")),
                    verified=bool(res.get("verified", True)),
                    proof=str(res.get("proof", "readback")),
                )
            )
        else:
            # Operation succeeded, record return value or requested value
            after_val = res
            if after_val is None and "value" in op_args:
                after_val = op_args["value"]
            changes.append(
                Change(
                    target=target,
                    before=None,
                    after=after_val,
                    verified=True,
                    proof="readback",
                )
            )

    all_ok = len(warnings) == 0 and all(c.verified for c in changes)
    return WriteReport(
        ok=all_ok,
        changes=changes,
        warnings=warnings,
        journal_id=journal_id,
    )


class BaseBatchContext:
    """Base collector for batch operation calls."""

    def __init__(self) -> None:
        self._ops: list[dict[str, Any]] = []
        self.report: WriteReport | None = None

    def add(self: T, op: str, args: dict[str, Any] | None = None) -> T:
        """Add an operation with arguments dict to the batch."""
        self._ops.append({"op": op, "args": dict(args) if args else {}})
        return self

    def call(self: T, op: str, *args: Any, **kwargs: Any) -> T:
        """Add an operation with flexible positional or keyword arguments to the batch."""
        call_args: dict[str, Any] = {}
        if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            call_args = dict(args[0])
        elif kwargs and not args:
            call_args = dict(kwargs)
        elif args:
            call_args = {"args": list(args), **kwargs}
        elif kwargs:
            call_args = dict(kwargs)
        return self.add(op, call_args)

    @property
    def ops(self) -> list[dict[str, Any]]:
        """Return shallow copy of recorded operations."""
        return list(self._ops)


class AsyncBatchContext(BaseBatchContext):
    """Asynchronous context manager collecting operations for a single wire batch."""

    def __init__(self, session: Any) -> None:
        super().__init__()
        self._session = session

    async def __aenter__(self) -> AsyncBatchContext:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            return
        if not self._ops:
            self.report = WriteReport(ok=True, changes=[], warnings=[])
            return
        results = await self._session.batch(self._ops)
        self.report = build_write_report(results, self._ops)


class SyncBatchContext(BaseBatchContext):
    """Synchronous context manager collecting operations for a single wire batch."""

    def __init__(self, portal: Any, session: Any) -> None:
        super().__init__()
        self._portal = portal
        self._session = session

    def __enter__(self) -> SyncBatchContext:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            return
        if not self._ops:
            self.report = WriteReport(ok=True, changes=[], warnings=[])
            return
        results = self._portal.call(self._session.batch, self._ops)
        self.report = build_write_report(results, self._ops)


# Public alias
BatchContext = AsyncBatchContext

__all__ = [
    "AsyncBatchContext",
    "BaseBatchContext",
    "BatchContext",
    "Change",
    "SyncBatchContext",
    "WriteReport",
    "build_write_report",
]
