"""Typed constants and enums for FL Studio MIDI scripting API.

Exports FPT_* global transport commands, midi.* event constants, UF_* undo flags,
PME_* flags, and REC_* flags per 05_l0c_device_script_manifest.md §16.
Generated deterministically by studiobridge.manifest.codegen. Do not edit manually.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag


class FPT(IntEnum):
    """Global transport command enum for transport.globalTransport()."""

    FPT_TrackJog = 2
    FPT_TempoJog = 3
    FPT_TapTempo = 4
    FPT_FPT = 6
    FPT_Mute = 15
    FPT_Mode = 16
    FPT_Undo = 17
    FPT_UndoJog = 18
    FPT_F1 = 40
    FPT_F2 = 41
    FPT_F3 = 42
    FPT_F4 = 43
    FPT_F5 = 44
    FPT_F6 = 45
    FPT_F7 = 46
    FPT_F8 = 47
    FPT_F9 = 48
    FPT_F10 = 49
    FPT_Enter = 50
    FPT_Escape = 51
    FPT_Yes = 52
    FPT_No = 53
    FPT_Cut = 60
    FPT_Copy = 61
    FPT_Paste = 62
    FPT_Insert = 63
    FPT_Delete = 64
    FPT_NextWindow = 70
    FPT_WindowJog = 71
    FPT_MixerWindowJog = 72
    FPT_ChannelWindowJog = 73
    FPT_ArrangerWindowJog = 74
    FPT_Save = 92
    FPT_SaveNew = 93
    FPT_Jog = 100
    FPT_Jog2 = 101
    FPT_Tempo = 102
    FPT_Play = 104
    FPT_Stop = 105
    FPT_Record = 106
    FPT_Pattern = 107
    FPT_Song = 108
    FPT_Loop = 109
    FPT_WaitKey = 111
    FPT_Rewind = 112
    FPT_FastForward = 113
    FPT_Metronome = 114
    FPT_CountDown = 115
    FPT_Overdub = 116
    FPT_LoopRecord = 117
    FPT_StepEdit = 118
    FPT_PunchIn = 119
    FPT_PunchOut = 120


class UF(IntFlag):
    """Undo flags for general.saveUndo()."""

    UF_None = 0
    UF_Cancel = 1
    UF_Reopen = 2
    UF_Direct = 4
    UF_Knob = 8
    UF_Audio = 16
    UF_Plugin = 32


class PME(IntFlag):
    """Parameter edit / process message event flags."""

    PME_None = 0
    PME_Live = 1
    PME_Internal = 2
    PME_Ghost = 4
    PME_Auto = 8
    PME_Process = 16
    PME_FromMIDI = 32


class REC(IntFlag):
    """Recording destination flags."""

    REC_None = 0
    REC_Audio = 1
    REC_Score = 2
    REC_Automation = 4


class MidiMsg(IntEnum):
    """Standard MIDI status bytes and event message identifiers."""

    TrkId_Master = 0
    MIDI_NOTEOFF = 0x80
    MIDI_NOTEON = 0x90
    MIDI_KEYAFTERTOUCH = 0xA0
    MIDI_CONTROLCHANGE = 0xB0
    MIDI_PROGRAMCHANGE = 0xC0
    MIDI_CHANNELAFTERTOUCH = 0xD0
    MIDI_PITCHBEND = 0xE0
    MIDI_SYSEX = 0xF0
    MIDI_SYSTEMMESSAGE = 0xF0
    MIDI_TIME_CODE = 0xF1
    MIDI_SONG_POS_POINTER = 0xF2
    MIDI_SONG_SELECT = 0xF3
    MIDI_TUNE_REQUEST = 0xF6
    MIDI_EOX = 0xF7
    MIDI_TIMING_CLOCK = 0xF8
    MIDI_START = 0xFA
    MIDI_CONTINUE = 0xFB
    MIDI_STOP = 0xFC
    MIDI_ACTIVE_SENSING = 0xFE
    MIDI_SYSTEM_RESET = 0xFF


class midi:
    """Namespace matching FL Studio's built-in midi module constants."""

    TrkId_Master: int = 0
    MIDI_NOTEOFF: int = 0x80
    MIDI_NOTEON: int = 0x90
    MIDI_KEYAFTERTOUCH: int = 0xA0
    MIDI_CONTROLCHANGE: int = 0xB0
    MIDI_PROGRAMCHANGE: int = 0xC0
    MIDI_CHANNELAFTERTOUCH: int = 0xD0
    MIDI_PITCHBEND: int = 0xE0
    MIDI_SYSEX: int = 0xF0
    MIDI_SYSTEMMESSAGE: int = 0xF0
    MIDI_TIME_CODE: int = 0xF1
    MIDI_SONG_POS_POINTER: int = 0xF2
    MIDI_SONG_SELECT: int = 0xF3
    MIDI_TUNE_REQUEST: int = 0xF6
    MIDI_EOX: int = 0xF7
    MIDI_TIMING_CLOCK: int = 0xF8
    MIDI_START: int = 0xFA
    MIDI_CONTINUE: int = 0xFB
    MIDI_STOP: int = 0xFC
    MIDI_ACTIVE_SENSING: int = 0xFE
    MIDI_SYSTEM_RESET: int = 0xFF


FPT_ArrangerWindowJog = FPT.FPT_ArrangerWindowJog
FPT_ChannelWindowJog = FPT.FPT_ChannelWindowJog
FPT_Copy = FPT.FPT_Copy
FPT_CountDown = FPT.FPT_CountDown
FPT_Cut = FPT.FPT_Cut
FPT_Delete = FPT.FPT_Delete
FPT_Enter = FPT.FPT_Enter
FPT_Escape = FPT.FPT_Escape
FPT_F1 = FPT.FPT_F1
FPT_F10 = FPT.FPT_F10
FPT_F2 = FPT.FPT_F2
FPT_F3 = FPT.FPT_F3
FPT_F4 = FPT.FPT_F4
FPT_F5 = FPT.FPT_F5
FPT_F6 = FPT.FPT_F6
FPT_F7 = FPT.FPT_F7
FPT_F8 = FPT.FPT_F8
FPT_F9 = FPT.FPT_F9
FPT_FPT = FPT.FPT_FPT
FPT_FastForward = FPT.FPT_FastForward
FPT_Insert = FPT.FPT_Insert
FPT_Jog = FPT.FPT_Jog
FPT_Jog2 = FPT.FPT_Jog2
FPT_Loop = FPT.FPT_Loop
FPT_LoopRecord = FPT.FPT_LoopRecord
FPT_Metronome = FPT.FPT_Metronome
FPT_MixerWindowJog = FPT.FPT_MixerWindowJog
FPT_Mode = FPT.FPT_Mode
FPT_Mute = FPT.FPT_Mute
FPT_NextWindow = FPT.FPT_NextWindow
FPT_No = FPT.FPT_No
FPT_Overdub = FPT.FPT_Overdub
FPT_Paste = FPT.FPT_Paste
FPT_Pattern = FPT.FPT_Pattern
FPT_Play = FPT.FPT_Play
FPT_PunchIn = FPT.FPT_PunchIn
FPT_PunchOut = FPT.FPT_PunchOut
FPT_Record = FPT.FPT_Record
FPT_Rewind = FPT.FPT_Rewind
FPT_Save = FPT.FPT_Save
FPT_SaveNew = FPT.FPT_SaveNew
FPT_Song = FPT.FPT_Song
FPT_StepEdit = FPT.FPT_StepEdit
FPT_Stop = FPT.FPT_Stop
FPT_TapTempo = FPT.FPT_TapTempo
FPT_Tempo = FPT.FPT_Tempo
FPT_TempoJog = FPT.FPT_TempoJog
FPT_TrackJog = FPT.FPT_TrackJog
FPT_Undo = FPT.FPT_Undo
FPT_UndoJog = FPT.FPT_UndoJog
FPT_WaitKey = FPT.FPT_WaitKey
FPT_WindowJog = FPT.FPT_WindowJog
FPT_Yes = FPT.FPT_Yes
UF_Audio = UF.UF_Audio
UF_Cancel = UF.UF_Cancel
UF_Direct = UF.UF_Direct
UF_Knob = UF.UF_Knob
UF_None = UF.UF_None
UF_Plugin = UF.UF_Plugin
UF_Reopen = UF.UF_Reopen
PME_Auto = PME.PME_Auto
PME_FromMIDI = PME.PME_FromMIDI
PME_Ghost = PME.PME_Ghost
PME_Internal = PME.PME_Internal
PME_Live = PME.PME_Live
PME_None = PME.PME_None
PME_Process = PME.PME_Process
REC_Audio = REC.REC_Audio
REC_Automation = REC.REC_Automation
REC_None = REC.REC_None
REC_Score = REC.REC_Score
MIDI_ACTIVE_SENSING = midi.MIDI_ACTIVE_SENSING
MIDI_CHANNELAFTERTOUCH = midi.MIDI_CHANNELAFTERTOUCH
MIDI_CONTINUE = midi.MIDI_CONTINUE
MIDI_CONTROLCHANGE = midi.MIDI_CONTROLCHANGE
MIDI_EOX = midi.MIDI_EOX
MIDI_KEYAFTERTOUCH = midi.MIDI_KEYAFTERTOUCH
MIDI_NOTEOFF = midi.MIDI_NOTEOFF
MIDI_NOTEON = midi.MIDI_NOTEON
MIDI_PITCHBEND = midi.MIDI_PITCHBEND
MIDI_PROGRAMCHANGE = midi.MIDI_PROGRAMCHANGE
MIDI_SONG_POS_POINTER = midi.MIDI_SONG_POS_POINTER
MIDI_SONG_SELECT = midi.MIDI_SONG_SELECT
MIDI_START = midi.MIDI_START
MIDI_STOP = midi.MIDI_STOP
MIDI_SYSEX = midi.MIDI_SYSEX
MIDI_SYSTEMMESSAGE = midi.MIDI_SYSTEMMESSAGE
MIDI_SYSTEM_RESET = midi.MIDI_SYSTEM_RESET
MIDI_TIME_CODE = midi.MIDI_TIME_CODE
MIDI_TIMING_CLOCK = midi.MIDI_TIMING_CLOCK
MIDI_TUNE_REQUEST = midi.MIDI_TUNE_REQUEST
TrkId_Master = midi.TrkId_Master

__all__ = [
    "FPT",
    "UF",
    "PME",
    "REC",
    "MidiMsg",
    "midi",
    "FPT_ArrangerWindowJog",
    "FPT_ChannelWindowJog",
    "FPT_Copy",
    "FPT_CountDown",
    "FPT_Cut",
    "FPT_Delete",
    "FPT_Enter",
    "FPT_Escape",
    "FPT_F1",
    "FPT_F10",
    "FPT_F2",
    "FPT_F3",
    "FPT_F4",
    "FPT_F5",
    "FPT_F6",
    "FPT_F7",
    "FPT_F8",
    "FPT_F9",
    "FPT_FPT",
    "FPT_FastForward",
    "FPT_Insert",
    "FPT_Jog",
    "FPT_Jog2",
    "FPT_Loop",
    "FPT_LoopRecord",
    "FPT_Metronome",
    "FPT_MixerWindowJog",
    "FPT_Mode",
    "FPT_Mute",
    "FPT_NextWindow",
    "FPT_No",
    "FPT_Overdub",
    "FPT_Paste",
    "FPT_Pattern",
    "FPT_Play",
    "FPT_PunchIn",
    "FPT_PunchOut",
    "FPT_Record",
    "FPT_Rewind",
    "FPT_Save",
    "FPT_SaveNew",
    "FPT_Song",
    "FPT_StepEdit",
    "FPT_Stop",
    "FPT_TapTempo",
    "FPT_Tempo",
    "FPT_TempoJog",
    "FPT_TrackJog",
    "FPT_Undo",
    "FPT_UndoJog",
    "FPT_WaitKey",
    "FPT_WindowJog",
    "FPT_Yes",
    "MIDI_ACTIVE_SENSING",
    "MIDI_CHANNELAFTERTOUCH",
    "MIDI_CONTINUE",
    "MIDI_CONTROLCHANGE",
    "MIDI_EOX",
    "MIDI_KEYAFTERTOUCH",
    "MIDI_NOTEOFF",
    "MIDI_NOTEON",
    "MIDI_PITCHBEND",
    "MIDI_PROGRAMCHANGE",
    "MIDI_SONG_POS_POINTER",
    "MIDI_SONG_SELECT",
    "MIDI_START",
    "MIDI_STOP",
    "MIDI_SYSEX",
    "MIDI_SYSTEMMESSAGE",
    "MIDI_SYSTEM_RESET",
    "MIDI_TIME_CODE",
    "MIDI_TIMING_CLOCK",
    "MIDI_TUNE_REQUEST",
    "PME_Auto",
    "PME_FromMIDI",
    "PME_Ghost",
    "PME_Internal",
    "PME_Live",
    "PME_None",
    "PME_Process",
    "REC_Audio",
    "REC_Automation",
    "REC_None",
    "REC_Score",
    "TrkId_Master",
    "UF_Audio",
    "UF_Cancel",
    "UF_Direct",
    "UF_Knob",
    "UF_None",
    "UF_Plugin",
    "UF_Reopen",
]
