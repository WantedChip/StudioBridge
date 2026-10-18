"""MIDI port abstractions, WinMM ctypes backend, discovery, and fake loopback ports."""

from studiobridge.ports.base import (
    MidiPort,
    MidiPortInfo,
    PortStats,
)
from studiobridge.ports.discovery import (
    PortResolver,
)
from studiobridge.ports.fake import (
    FakeMidiPort,
)
from studiobridge.ports.winmm import (
    MIDIHDR,
    MIDIINCAPSW,
    MIDIOUTCAPSW,
    WinMmMidiPort,
    map_winmm_error,
    setup_winmm_signatures,
)
from studiobridge.ports.wms import (
    WmsDetector,
    WmsDiagnostics,
)

__all__ = [
    "FakeMidiPort",
    "MIDIHDR",
    "MIDIINCAPSW",
    "MIDIOUTCAPSW",
    "MidiPort",
    "MidiPortInfo",
    "PortResolver",
    "PortStats",
    "WinMmMidiPort",
    "WmsDetector",
    "WmsDiagnostics",
    "map_winmm_error",
    "setup_winmm_signatures",
]
