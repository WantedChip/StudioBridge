"""Unit and integration tests for StudioBridge transactions, checkpoints, and rollback guarantees.

Verifies [TXN-01..02]:
- Exceptions inside with fl.transaction(): trigger automatic rollback to initial values.
- Automatic rollback restores mixer volume, pan, and mute states cleanly.
- Repeated mutations within a transaction restore to the initial before value.
- Successful transactions commit all writes and release the writer lease cleanly.
- Each transaction accurately reports its guarantee level (G0, G1, or G2).
- Nested transactions flatten into outer transaction without orphan locks.
- Synchronous (Studio) and asynchronous (AsyncStudio) transaction execution.
"""

from __future__ import annotations

import anyio
import pytest

from studiobridge import (
    AsyncStudio,
    RollbackGuarantee,
    RollbackReport,
    Studio,
    Transaction,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.txn import TargetState


def test_rollback_guarantee_equality_and_properties() -> None:
    """Verify RollbackGuarantee enum equality comparisons across strings, levels, and values."""
    assert RollbackGuarantee.G0 == "G0"
    assert RollbackGuarantee.G0 == "none"
    assert RollbackGuarantee.G0.level == "G0"
    assert RollbackGuarantee.G0.value == "none"

    assert RollbackGuarantee.G1 == "G1"
    assert RollbackGuarantee.G1 == "best_effort"
    assert RollbackGuarantee.G1.level == "G1"
    assert RollbackGuarantee.G1.value == "best_effort"

    assert RollbackGuarantee.G2 == "G2"
    assert RollbackGuarantee.G2 == "verified"
    assert RollbackGuarantee.G2.level == "G2"
    assert RollbackGuarantee.G2.value == "verified"

    assert RollbackGuarantee.from_value("g0") == RollbackGuarantee.G0
    assert RollbackGuarantee.from_value("G1") == RollbackGuarantee.G1
    assert RollbackGuarantee.from_value("verified") == RollbackGuarantee.G2


def test_successful_transaction_commit_sync(studio: Studio) -> None:
    """Verify synchronous transaction commits writes and releases writer lease cleanly."""
    with studio.transaction("balance_drums") as tx:
        assert isinstance(tx, Transaction)
        assert tx.is_nested is False
        assert tx.committed is False

        studio.mixer.set_volume(1, 0.5)
        studio.mixer.set_pan(1, -0.3)

        assert studio.mixer.get_volume(1) == 0.5
        assert studio.mixer.get_pan(1) == -0.3

    # On clean exit: committed and writer lease released
    assert tx.committed is True
    assert tx.rolled_back is False
    assert tx.report is None
    assert studio.session.lease_holder is None

    # State persists after commit
    assert studio.mixer.get_volume(1) == 0.5
    assert studio.mixer.get_pan(1) == -0.3

    # Commit entry exists in mutation journal
    commit_entries = studio.session.journal.list(op="txn.commit")
    assert len(commit_entries) >= 1
    assert any("balance_drums" in str(e.details.get("name")) for e in commit_entries)


def test_automatic_rollback_on_exception_restores_volume_pan_mute(studio: Studio) -> None:
    """Verify exceptions inside transaction trigger rollback of volume, pan, and mute."""
    track_idx = 1
    # Verify initial baseline state
    studio.mixer.set_volume(track_idx, 0.8)
    studio.mixer.set_pan(track_idx, 0.0)
    studio.mixer.mute(track_idx, False)

    assert studio.mixer.get_volume(track_idx) == 0.8
    assert studio.mixer.get_pan(track_idx) == 0.0
    assert studio.mixer.is_muted(track_idx) is False

    tx_ref: Transaction | None = None
    with (
        pytest.raises(RuntimeError, match="Simulated mixer processing failure"),
        studio.transaction("faulty_mix") as tx,
    ):
        tx_ref = tx
        studio.mixer.set_volume(track_idx, 0.35)
        studio.mixer.set_pan(track_idx, 0.6)
        studio.mixer.mute(track_idx, True)

        # Assert intermediate mutations took effect inside block
        assert studio.mixer.get_volume(track_idx) == 0.35
        assert studio.mixer.get_pan(track_idx) == 0.6
        assert studio.mixer.is_muted(track_idx) is True

        raise RuntimeError("Simulated mixer processing failure")

    # Assert transaction rolled back and generated report
    assert tx_ref is not None
    assert tx_ref.rolled_back is True
    assert tx_ref.committed is False
    assert tx_ref.report is not None
    report: RollbackReport = tx_ref.report

    assert report.ok is True
    assert report.guarantee == RollbackGuarantee.G2
    assert report.guarantee == "G2"
    assert report.guarantee == "verified"
    assert report.guarantee.level == "G2"

    # Verify all 3 parameters restored to exact initial values
    assert studio.mixer.get_volume(track_idx) == 0.8
    assert studio.mixer.get_pan(track_idx) == 0.0
    assert studio.mixer.is_muted(track_idx) is False

    # Verify lease released without orphan locks
    assert studio.session.lease_holder is None

    # Verify journal recorded rollback
    rb_entries = studio.session.journal.list(op="txn.rollback")
    assert len(rb_entries) >= 1
    assert any("faulty_mix" in str(e.details.get("name")) for e in rb_entries)


def test_repeated_mutations_restore_to_initial_before_value(studio: Studio) -> None:
    """Verify multiple mutations to the same target restore to the initial before value."""
    track_idx = 2
    studio.mixer.set_volume(track_idx, 0.8)
    assert studio.mixer.get_volume(track_idx) == 0.8

    tx_ref: Transaction | None = None
    with (
        pytest.raises(ValueError, match="abort multi-write"),
        studio.transaction("multi_write") as tx,
    ):
        tx_ref = tx
        # Change 0.8 -> 0.6
        studio.mixer.set_volume(track_idx, 0.6)
        assert studio.mixer.get_volume(track_idx) == 0.6

        # Change 0.6 -> 0.4
        studio.mixer.set_volume(track_idx, 0.4)
        assert studio.mixer.get_volume(track_idx) == 0.4

        # Change 0.4 -> 0.2
        studio.mixer.set_volume(track_idx, 0.2)
        assert studio.mixer.get_volume(track_idx) == 0.2

        raise ValueError("abort multi-write")

    assert tx_ref is not None
    assert tx_ref.rolled_back is True
    # Must restore to 0.8 (the initial before value), not 0.6 or 0.4
    assert studio.mixer.get_volume(track_idx) == 0.8
    assert studio.session.lease_holder is None


def test_manual_rollback_invocation(studio: Studio) -> None:
    """Verify explicit manual tx.rollback() triggers rollback and generates G2 report."""
    track_idx = 3
    studio.mixer.set_volume(track_idx, 0.8)

    with studio.transaction("manual_tx") as tx:
        studio.mixer.set_volume(track_idx, 0.15)
        assert studio.mixer.get_volume(track_idx) == 0.15

        report = tx.rollback()
        assert report.ok is True
        assert report.guarantee == RollbackGuarantee.G2
        assert report.guarantee == "G2"

    assert studio.mixer.get_volume(track_idx) == 0.8
    assert tx.rolled_back is True
    assert studio.session.lease_holder is None


def test_guarantee_level_reporting_g0_for_irreversible_operations(studio: Studio) -> None:
    """Verify transactions containing irreversible operations report G0 ('none') upon rollback."""
    with studio.transaction("irreversible_tx") as tx:
        studio.mixer.set_volume(1, 0.7)
        # Record a project save mutation (an irreversible operation)
        studio.session.safety.journal.record(
            op="project.save_new_version",
            target="project.file",
            before=None,
            after="song_v2.flp",
            proof="none",
        )
        assert tx.guarantee == RollbackGuarantee.G0

        report = tx.rollback()
        assert report.ok is False
        assert report.guarantee == RollbackGuarantee.G0
        assert report.guarantee == "G0"
        assert report.guarantee == "none"
        assert report.guarantee.level == "G0"
        assert any("irreversible" in r.lower() for r in report.reasons)


def test_guarantee_level_reporting_g1_when_verification_fails(studio: Studio) -> None:
    """Verify transactions where target verification fails report G1 ('best_effort')."""
    with studio.transaction("unverified_tx") as tx:
        # Manually register a target that has an unmatchable initial before state
        target_state = TargetState(
            key="custom.target:val",
            target="custom.target",
            op="unsupported.fake_op",
            initial_before=12345,
        )
        tx._initial_targets[target_state.key] = target_state

        report = tx.rollback()
        assert report.ok is False
        assert report.guarantee == RollbackGuarantee.G1
        assert report.guarantee == "G1"
        assert report.guarantee == "best_effort"
        assert report.guarantee.level == "G1"
        assert len(report.unrestored) > 0


def test_nested_transactions_flatten_into_outer_transaction(studio: Studio) -> None:
    """Verify nested transactions flatten into outer transaction cleanly [TXN-02]."""
    studio.mixer.set_volume(1, 0.8)
    studio.mixer.set_pan(1, 0.0)
    studio.mixer.set_volume(2, 0.8)

    with studio.transaction("outer_tx") as tx_outer:
        assert tx_outer.is_nested is False
        assert studio.session.lease_holder is not None

        studio.mixer.set_volume(1, 0.45)

        with studio.transaction("inner_tx") as tx_inner:
            assert tx_inner.is_nested is True
            assert studio.session.lease_holder is not None

            studio.mixer.set_pan(1, -0.4)
            studio.mixer.set_volume(2, 0.35)

        # Inner transaction completed: outer transaction still holds lease!
        assert tx_inner.committed is True
        assert studio.session.lease_holder is not None

        studio.mixer.mute(1, True)

    # Outer transaction committed: lease released cleanly
    assert tx_outer.committed is True
    assert studio.session.lease_holder is None

    # All inner and outer modifications successfully applied
    assert studio.mixer.get_volume(1) == 0.45
    assert studio.mixer.get_pan(1) == -0.4
    assert studio.mixer.get_volume(2) == 0.35
    assert studio.mixer.is_muted(1) is True


def test_nested_transaction_exception_triggers_full_rollback_no_orphan_locks(
    studio: Studio,
) -> None:
    """Verify nested transaction failure triggers outer rollback without orphan locks [TXN-02]."""
    studio.mixer.set_volume(1, 0.8)
    studio.mixer.set_pan(1, 0.0)

    with (
        pytest.raises(RuntimeError, match="nested failure"),
        studio.transaction("outer_rollback"),
    ):
        studio.mixer.set_volume(1, 0.25)

        with studio.transaction("inner_rollback"):
            studio.mixer.set_pan(1, 0.75)
            raise RuntimeError("nested failure")

    # Assert both outer and inner mutations were cleanly rolled back
    assert studio.mixer.get_volume(1) == 0.8
    assert studio.mixer.get_pan(1) == 0.0

    # Assert no orphan locks remain
    assert studio.session.lease_holder is None


def test_transaction_lease_extension(studio: Studio) -> None:
    """Verify writer lease extension during transaction lifecycle."""
    with studio.transaction("long_tx", timeout=120.0) as tx:
        res = tx.extend_lease(ttl=180.0)
        assert isinstance(res, dict)
        assert studio.session.lease_holder is not None

    assert studio.session.lease_holder is None


def test_transaction_in_readonly_mode_elevates_and_restores(studio_readonly: Studio) -> None:
    """Verify transaction elevates mode for transaction scope and restores read_only on exit."""
    assert studio_readonly.mode == "read_only"
    assert studio_readonly.session.lease_holder is None

    with studio_readonly.transaction("temp_write"):
        assert studio_readonly.mode in ("write", "write_autonomous")
        assert studio_readonly.session.lease_holder is not None

        studio_readonly.mixer.set_volume(1, 0.55)
        assert studio_readonly.mixer.get_volume(1) == 0.55

    # Restored to read_only and lease released cleanly
    assert studio_readonly.mode == "read_only"
    assert studio_readonly.session.lease_holder is None


def test_async_transaction_lifecycle(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify asynchronous transaction commit, rollback, and guarantee reporting under anyio."""
    port_sdk, _ = running_emulator

    async def _run_async_test() -> None:
        async with AsyncStudio.connect(
            embedded=True, port=port_sdk, secret=sdk_secret, mode="write"
        ) as fl:
            # 1. Async commit test
            async with fl.transaction("async_commit") as tx1:
                assert tx1.is_nested is False
                await fl.mixer.set_volume(4, 0.65)

            assert tx1.committed is True
            assert await fl.mixer.get_volume(4) == 0.65
            assert fl.session.lease_holder is None

            # 2. Async rollback test
            tx2_ref: Transaction | None = None
            try:
                async with fl.transaction("async_rollback") as tx2:
                    tx2_ref = tx2
                    await fl.mixer.set_volume(4, 0.2)
                    raise RuntimeError("async failure")
            except RuntimeError:
                pass

            assert tx2_ref is not None
            assert tx2_ref.rolled_back is True
            assert tx2_ref.report is not None
            assert tx2_ref.report.guarantee == RollbackGuarantee.G2
            # Value restored back to 0.65
            assert await fl.mixer.get_volume(4) == 0.65
            assert fl.session.lease_holder is None

    anyio.run(_run_async_test)
