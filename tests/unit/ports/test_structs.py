"""Unit tests for WinMM ctypes structures and 64-bit alignment invariants [PORT-12]."""

import ctypes

from studiobridge.ports.winmm import (
    MIDIHDR,
    MIDIINCAPSW,
    MIDIOUTCAPSW,
)


def test_midihdr_sizeof_64bit() -> None:
    """Assert sizeof(MIDIHDR) is exactly 112 bytes on 64-bit platforms [PORT-12]."""
    is_64bit = ctypes.sizeof(ctypes.c_void_p) == 8
    if is_64bit:
        assert ctypes.sizeof(MIDIHDR) == 112, (
            f"Expected sizeof(MIDIHDR) == 112 on 64-bit, got {ctypes.sizeof(MIDIHDR)}"
        )
    else:
        assert ctypes.sizeof(MIDIHDR) == 64, (
            f"Expected sizeof(MIDIHDR) == 64 on 32-bit, got {ctypes.sizeof(MIDIHDR)}"
        )


def test_midihdr_field_offsets() -> None:
    """Validate struct packing and exact field offsets matching mmeapi.h under pack(1)."""
    assert MIDIHDR._pack_ == 1

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        # 64-bit offsets with pack(1)
        assert MIDIHDR.lpData.offset == 0
        assert MIDIHDR.dwBufferLength.offset == 8
        assert MIDIHDR.dwBytesRecorded.offset == 12
        assert MIDIHDR.dwUser.offset == 16
        assert MIDIHDR.dwFlags.offset == 24
        assert MIDIHDR.lpNext.offset == 28
        assert MIDIHDR.reserved.offset == 36
        assert MIDIHDR.dwOffset.offset == 44
        assert MIDIHDR.dwReserved.offset == 48
        # dwReserved is c_size_t * 8 = 64 bytes
        assert ctypes.sizeof(ctypes.c_size_t * 8) == 64
        assert MIDIHDR.dwReserved.size == 64


def test_midihdr_instantiation_and_field_assignment() -> None:
    """Verify that MIDIHDR fields can be instantiated and mutated without memory faults."""
    hdr = MIDIHDR()
    assert hdr.lpData is None
    assert hdr.dwBufferLength == 0
    assert hdr.dwBytesRecorded == 0
    assert hdr.dwUser == 0
    assert hdr.dwFlags == 0
    assert hdr.dwOffset == 0

    dummy_buf = (ctypes.c_char * 64)(*b"test sysex data buffer payload")
    hdr.lpData = ctypes.cast(dummy_buf, ctypes.c_void_p)
    hdr.dwBufferLength = 64
    hdr.dwBytesRecorded = 30
    hdr.dwUser = 42
    hdr.dwFlags = 1

    assert hdr.dwBufferLength == 64
    assert hdr.dwBytesRecorded == 30
    assert hdr.dwUser == 42
    assert hdr.dwFlags == 1
    assert hdr.lpData == ctypes.cast(dummy_buf, ctypes.c_void_p).value


def test_midiincapsw_struct_layout() -> None:
    """Validate MIDIINCAPSW struct size and field offsets."""
    assert MIDIINCAPSW._pack_ == 1
    # 2 + 2 + 4 + (32 * 2 = 64) + 4 = 76 bytes
    assert ctypes.sizeof(MIDIINCAPSW) == 76

    caps = MIDIINCAPSW()
    caps.wMid = 0x0047
    caps.wPid = 0x0001
    caps.vDriverVersion = (1 << 8) | 2
    caps.szPname = "Test Port In"
    caps.dwSupport = 0

    assert caps.wMid == 0x0047
    assert caps.wPid == 0x0001
    assert caps.szPname == "Test Port In"


def test_midioutcapsw_struct_layout() -> None:
    """Validate MIDIOUTCAPSW struct size and field offsets."""
    assert MIDIOUTCAPSW._pack_ == 1
    # 2 + 2 + 4 + 64 + 2 + 2 + 2 + 2 + 4 = 84 bytes
    assert ctypes.sizeof(MIDIOUTCAPSW) == 84

    caps = MIDIOUTCAPSW()
    caps.wMid = 0x0047
    caps.wPid = 0x0002
    caps.vDriverVersion = (2 << 8) | 0
    caps.szPname = "Test Port Out"
    caps.wTechnology = 1
    caps.wVoices = 16
    caps.wNotes = 128
    caps.wChannelMask = 0xFFFF
    caps.dwSupport = 0

    assert caps.szPname == "Test Port Out"
    assert caps.wVoices == 16
    assert caps.wNotes == 128
