"""Unit and integration tests for Transport namespace.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) transport interfaces:
- play(), stop(), record(), is_playing()
- get_tempo(), set_tempo(bpm)
- get_time(), set_time(pos)
- get_loop_mode(), set_loop_mode(mode)
- metronome(), time_signature()
- Verified return structure (plane="live", proof="readback", settled=True)
- ReadOnlyError enforcement in read_only mode
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    ReadOnlyError,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_transport_playback_controls(studio: Studio) -> None:
    """Verify transport play, stop, record, and is_playing controls in sync Studio."""
    fl = studio
    assert fl.transport.is_playing() is False

    # Play
    v_play = fl.transport.play()
    assert isinstance(v_play, Verified)
    assert v_play.value is True
    assert v_play.verified is True
    assert v_play.plane == "live"
    assert v_play.proof == "readback"
    assert fl.transport.is_playing() is True

    # Stop
    v_stop = fl.transport.stop()
    assert isinstance(v_stop, Verified)
    assert v_stop.value is False
    assert v_stop.verified is True
    assert fl.transport.is_playing() is False

    # Record toggle
    v_rec = fl.transport.record()
    assert isinstance(v_rec, Verified)
    assert v_rec.verified is True
    assert v_rec.plane == "live"


def test_sync_transport_tempo(studio: Studio) -> None:
    """Verify tempo reading and writing with Verified return contract."""
    fl = studio
    initial_tempo = fl.transport.get_tempo()
    assert isinstance(initial_tempo, float)
    assert initial_tempo > 0.0

    v = fl.transport.set_tempo(132.5)
    assert isinstance(v, Verified)
    assert v.requested == 132.5
    assert abs(v.value - 132.5) < 0.1
    assert v.verified is True
    assert v.settled is True
    assert v.proof == "readback"
    assert v.fp == fl.fp

    # Read back explicitly
    assert abs(fl.transport.get_tempo() - 132.5) < 0.1


def test_sync_transport_position(studio: Studio) -> None:
    """Verify song position setting and reading."""
    fl = studio
    v = fl.transport.set_time(0.25)
    assert isinstance(v, Verified)
    assert v.requested == 0.25
    assert abs(v.value - 0.25) < 0.05
    assert v.verified is True

    pos = fl.transport.get_time()
    assert abs(pos - 0.25) < 0.05


def test_sync_transport_loop_and_metronome(studio: Studio) -> None:
    """Verify loop mode, metronome toggle, and time signature queries."""
    fl = studio
    # Loop mode
    v_loop = fl.transport.set_loop_mode(1)
    assert isinstance(v_loop, Verified)
    assert v_loop.value == 1
    assert fl.transport.get_loop_mode() == 1

    v_loop0 = fl.transport.set_loop_mode(0)
    assert v_loop0.value == 0
    assert fl.transport.get_loop_mode() == 0

    # Metronome
    v_metro = fl.transport.metronome(True)
    assert isinstance(v_metro, Verified)
    assert v_metro.value is True

    v_metro_off = fl.transport.metronome(False)
    assert v_metro_off.value is False

    # Time signature
    num, den = fl.transport.time_signature()
    assert isinstance(num, int) and num > 0
    assert isinstance(den, int) and den > 0


def test_sync_transport_readonly_guard(studio_readonly: Studio) -> None:
    """Verify mutating transport operations raise ReadOnlyError in read_only mode."""
    fl = studio_readonly
    # Non-mutating methods succeed
    assert fl.transport.is_playing() is False
    assert fl.transport.get_tempo() > 0.0
    assert fl.transport.get_loop_mode() in (0, 1)
    assert len(fl.transport.time_signature()) == 2

    # Mutating methods fail with ReadOnlyError
    with pytest.raises(ReadOnlyError):
        fl.transport.play()

    with pytest.raises(ReadOnlyError):
        fl.transport.stop()

    with pytest.raises(ReadOnlyError):
        fl.transport.set_tempo(120.0)

    with pytest.raises(ReadOnlyError):
        fl.transport.set_time(0.5)

    with pytest.raises(ReadOnlyError):
        fl.transport.set_loop_mode(1)

    with pytest.raises(ReadOnlyError):
        fl.transport.metronome(True)


@pytest.mark.anyio
async def test_async_transport_operations(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify all AsyncTransport operations under anyio event loop."""
    port_sdk, _ = running_emulator
    async with AsyncStudio.connect(
        embedded=True, port=port_sdk, secret=sdk_secret, mode="write"
    ) as fl:
        # Playback
        v_play = await fl.transport.play()
        assert v_play.value is True
        assert await fl.transport.is_playing() is True

        v_stop = await fl.transport.stop()
        assert v_stop.value is False
        assert await fl.transport.is_playing() is False

        # Tempo
        v_tempo = await fl.transport.set_tempo(144.0)
        assert abs(v_tempo.value - 144.0) < 0.1
        assert abs(await fl.transport.get_tempo() - 144.0) < 0.1

        # Position
        v_pos = await fl.transport.set_time(0.5)
        assert abs(v_pos.value - 0.5) < 0.05
        assert abs(await fl.transport.get_time() - 0.5) < 0.05

        # Loop mode
        v_loop = await fl.transport.set_loop_mode(1)
        assert v_loop.value == 1
        assert await fl.transport.get_loop_mode() == 1

        # Metronome & Time Signature
        v_metro = await fl.transport.metronome(True)
        assert v_metro.value is True
        sig = await fl.transport.time_signature()
        assert sig == (4, 4)
