"""Unit tests for batch execution and WriteReport builder.

Verifies 09_l1_sdk.md §3.1, §4, and v0.2.3 Definition of Done:
- fl.batch() collects multiple calls into a single wire batch and returns WriteReport.
- Change dataclass records targets, values, and verification status.
- Sync and async batch execution.
- Empty batch and partial failure handling.
"""

from __future__ import annotations

from typing import Any

import pytest

from studiobridge.sdk.batch import (
    Change,
    WriteReport,
    build_write_report,
)
from studiobridge.sdk.client import AsyncStudio, Studio


def test_change_and_write_report_serialization() -> None:
    """Verify Change and WriteReport dataclass properties and serialization."""
    change = Change(
        target="mixer.setTrackVolume",
        before=0.8,
        after=0.65,
        verified=True,
        proof="readback",
    )
    assert change.target == "mixer.setTrackVolume"
    assert change.before == 0.8
    assert change.after == 0.65
    assert change.verified is True
    assert change.proof == "readback"

    c_dict = change.to_dict()
    assert c_dict["target"] == "mixer.setTrackVolume"
    assert c_dict["before"] == 0.8
    assert c_dict["after"] == 0.65

    report = WriteReport(
        ok=True,
        changes=[change],
        warnings=[],
        journal_id="j_12345",
    )
    assert report.ok is True
    assert len(report.changes) == 1
    assert report.journal_id == "j_12345"

    r_dict = report.to_dict()
    assert r_dict["ok"] is True
    assert len(r_dict["changes"]) == 1
    assert r_dict["journal_id"] == "j_12345"


def test_build_write_report_success() -> None:
    """build_write_report correctly correlates operations with results."""
    ops = [
        {"op": "transport.setLoopMode", "args": {"mode": 1}},
        {"op": "mixer.setTrackVolume", "args": {"track": 1, "value": 0.75}},
    ]
    results = [
        {"verified": True, "before": 0, "after": 1},
        {"verified": True, "target": "mixer.track(1).volume", "before": 0.8, "after": 0.75},
    ]

    report = build_write_report(results, ops, journal_id="tx_001")
    assert report.ok is True
    assert len(report.changes) == 2
    assert report.changes[0].target == "transport.setLoopMode"
    assert report.changes[0].before == 0
    assert report.changes[0].after == 1
    assert report.changes[1].target == "mixer.track(1).volume"
    assert report.changes[1].after == 0.75
    assert len(report.warnings) == 0


def test_build_write_report_with_errors() -> None:
    """build_write_report marks ok=False and appends warnings when operations fail."""
    ops = [
        {"op": "mixer.setTrackVolume", "args": {"track": 0, "value": 0.5}},
        {"op": "mixer.setTrackVolume", "args": {"track": 999, "value": 0.5}},
    ]
    results = [
        0.5,
        {"ok": False, "err": "Track index 999 out of range"},
    ]

    report = build_write_report(results, ops)
    assert report.ok is False
    assert len(report.changes) == 2
    assert report.changes[0].verified is True
    assert report.changes[1].verified is False
    assert report.changes[1].error == "Track index 999 out of range"
    assert len(report.warnings) == 1


def test_sync_batch_execution() -> None:
    """Synchronous fl.batch() accumulates operations and executes as a single batch."""
    call_log: list[tuple[str, dict[str, Any]]] = []

    def mock_handler(op: str, args: dict[str, Any]) -> Any:
        call_log.append((op, args))
        if op == "mixer.setTrackVolume":
            return {"verified": True, "before": 0.8, "after": args.get("value", 0.5)}
        return True

    with Studio.connect(embedded=True, direct_handler=mock_handler, mode="write") as fl:
        with fl.batch() as b:
            b.call("ping")
            b.add("mixer.setTrackVolume", {"track": 1, "value": 0.7})

        assert b.report is not None
        assert b.report.ok is True
        assert len(b.report.changes) == 2
        assert len(call_log) == 2


@pytest.mark.anyio
async def test_async_batch_execution() -> None:
    """Asynchronous fl.batch() accumulates operations and executes as a single batch."""
    call_log: list[tuple[str, dict[str, Any]]] = []

    def mock_handler(op: str, args: dict[str, Any]) -> Any:
        call_log.append((op, args))
        return {"verified": True, "value": args.get("val", 1)}

    async with AsyncStudio.connect(embedded=True, direct_handler=mock_handler, mode="write") as fl:
        async with fl.batch() as b:
            b.call("test.op1", val=10)
            b.call("test.op2", val=20)
            b.call("test.op3", val=30)

        assert b.report is not None
        assert b.report.ok is True
        assert len(b.report.changes) == 3
        assert len(call_log) == 3
        assert b.report.changes[0].after == 10
        assert b.report.changes[1].after == 20
        assert b.report.changes[2].after == 30


def test_empty_batch_handling() -> None:
    """An empty batch block returns ok=True WriteReport without issuing device calls."""
    with Studio.connect(embedded=True) as fl:
        with fl.batch() as b:
            pass  # No ops added

        assert b.report is not None
        assert b.report.ok is True
        assert len(b.report.changes) == 0
        assert len(b.report.warnings) == 0


def test_batch_context_exception_suppression() -> None:
    """If an exception occurs inside the batch block, batch execution is aborted."""
    call_count = 0

    def mock_handler(op: str, args: dict[str, Any]) -> Any:
        nonlocal call_count
        call_count += 1
        return True

    with Studio.connect(embedded=True, direct_handler=mock_handler) as fl:
        batch_ctx = fl.batch()
        with pytest.raises(RuntimeError, match="user failure"), batch_ctx as b:
            b.call("ping")
            raise RuntimeError("user failure")

        # Report should not have executed batch because of exception
        assert batch_ctx.report is None
        assert call_count == 0
