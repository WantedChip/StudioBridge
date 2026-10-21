"""Unit tests for StudioBridge append-only mutation journal [SAF-03]."""

from __future__ import annotations

import json
import time
from pathlib import Path

from studiobridge.sdk.journal import JournalEntry, MutationJournal
from studiobridge.sdk.verification import verify_mutation


def test_journal_entry_serialization() -> None:
    """Verify JournalEntry serialization and deserialization."""
    entry = JournalEntry(
        entry_id="test_01",
        ts=time.time(),
        session_id="101",
        op="mixer.setTrackVolume",
        args={"index": 1, "volume": 0.8},
        before=0.5,
        after=0.8,
        verified=True,
        rolled_back=False,
        user="test_agent",
    )
    d = entry.to_dict()
    assert d["entry_id"] == "test_01"
    assert d["session_id"] == "101"
    assert d["op"] == "mixer.setTrackVolume"
    assert d["args"] == {"index": 1, "volume": 0.8}
    assert d["before"] == 0.5
    assert d["after"] == 0.8
    assert d["verified"] is True

    # Roundtrip from_dict
    parsed = JournalEntry.from_dict(d)
    assert parsed.entry_id == entry.entry_id
    assert parsed.session_id == entry.session_id
    assert parsed.op == entry.op
    assert parsed.args == entry.args
    assert parsed.verified == entry.verified


def test_mutation_journal_record_and_file_persistence(tmp_path: Path) -> None:
    """Verify MutationJournal records entries to JSONL on disk."""
    log_file = tmp_path / "journal_test.jsonl"
    journal = MutationJournal(session_id="session_42", log_path=log_file, user="agent_test")

    assert journal.count() == 0
    assert not log_file.exists()

    # Record first entry
    entry1 = journal.record(
        op="mixer.setTrackVolume",
        args={"index": 1, "volume": 0.75},
        before=0.5,
        after=0.75,
        verified=True,
    )
    assert entry1.op == "mixer.setTrackVolume"
    assert entry1.session_id == "session_42"
    assert journal.count() == 1
    assert log_file.exists()

    # Record second entry
    entry2 = journal.record(
        op="transport.setTempo",
        args={"bpm": 130.0},
        before=120.0,
        after=130.0,
        verified=True,
    )
    assert entry2.op == "transport.setTempo"
    assert journal.count() == 2

    # Check file contents directly
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed_json = json.loads(lines[0])
    assert parsed_json["op"] == "mixer.setTrackVolume"


def test_mutation_journal_list_filters(tmp_path: Path) -> None:
    """Verify MutationJournal.list with op and limit filters."""
    log_file = tmp_path / "journal_filter.jsonl"
    journal = MutationJournal(session_id="filter_session", log_path=log_file)

    t0 = time.time()
    journal.record(op="mixer.setTrackVolume", args={"index": 1, "volume": 0.7})
    journal.record(op="mixer.setTrackPan", args={"index": 1, "pan": 0.2})
    journal.record(op="mixer.setTrackVolume", args={"index": 2, "volume": 0.9})
    journal.record(op="transport.setTempo", args={"bpm": 125.0})

    # All entries
    all_entries = journal.list()
    assert len(all_entries) == 4

    # Filter by op
    vol_entries = journal.list(op="mixer.setTrackVolume")
    assert len(vol_entries) == 2
    assert all(e.op == "mixer.setTrackVolume" for e in vol_entries)

    # Limit
    limited = journal.list(limit=2)
    assert len(limited) == 2
    assert limited[-1].op == "transport.setTempo"

    # Filter by since
    since_entries = journal.list(since=t0 - 1.0)
    assert len(since_entries) == 4


def test_mutation_journal_export_and_clear(tmp_path: Path) -> None:
    """Verify MutationJournal export and clear operations."""
    log_file = tmp_path / "journal_export.jsonl"
    journal = MutationJournal(session_id="export_session", log_path=log_file)

    journal.record(op="patterns.setName", args={"index": 1, "name": "Bassline"})
    journal.record(op="patterns.setName", args={"index": 2, "name": "Chords"})
    assert journal.count() == 2

    export_target = tmp_path / "backup_journal.jsonl"
    journal.export(export_target)
    assert export_target.exists()
    assert len(export_target.read_text(encoding="utf-8").strip().splitlines()) == 2

    # Clear journal
    journal.clear()
    assert journal.count() == 0
    assert journal.list() == []


def test_verify_mutation_records_to_journal(tmp_path: Path) -> None:
    """Verify verify_mutation integration automatically appends to journal."""
    log_file = tmp_path / "verification_journal.jsonl"
    journal = MutationJournal(session_id="v_session", log_path=log_file)

    v = verify_mutation(
        fn="mixer.setTrackVolume",
        expected=0.8,
        actual=0.8,
        before=0.5,
        journal=journal,
        evidence={"index": 1},
    )
    assert v.verified is True
    assert journal.count() == 1
    entry = journal.list()[0]
    assert entry.op == "mixer.setTrackVolume"
    assert entry.before == 0.5
    assert entry.after == 0.8
    assert entry.verified is True
