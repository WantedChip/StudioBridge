"""Mock FL Studio builtins and API modules with realistic state.

Provides simulated FL Studio embedded environment and sandbox audit hooks / import blockers
restricting forbidden modules per [DEV-30].
"""

from __future__ import annotations

import types
from typing import Any

# Modules strictly forbidden in FL Studio controller script environment per [DEV-30]
FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "socket",
        "_socket",
        "ctypes",
        "_ctypes",
        "subprocess",
        "threading",
        "_thread",
        "select",
    }
)


class SandboxImportBlocker:
    """sys.meta_path import finder that blocks forbidden modules with ImportError."""

    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: Any = None,
    ) -> None:
        root_mod = fullname.split(".")[0]
        if root_mod in FORBIDDEN_MODULES:
            raise ImportError(
                f"Import of '{fullname}' is blocked by FL Studio controller script sandbox"
            )
        return None


class MockFLState:
    """Encapsulates the state of all mocked FL Studio modules."""

    def __init__(self) -> None:
        # device state
        self.device_assigned: bool = True
        self.device_port: int = 10
        self.device_name: str = "StudioBridge"
        self.device_sent_sysex: list[bytes] = []

        # transport state
        self.transport_playing: bool = False
        self.transport_recording: bool = False
        self.transport_song_pos: float = 0.0
        self.transport_song_length: float = 120.0
        self.transport_loop_mode: int = 0
        self.transport_tempo: float = 120.0
        self.transport_metronome: bool = False
        self.transport_time_signature: tuple[int, int] = (4, 4)

        # mixer state: 127 tracks
        self.mixer_tracks: list[dict[str, Any]] = []
        for i in range(127):
            name = "Master" if i == 0 else f"Insert {i}"
            self.mixer_tracks.append(
                {
                    "volume": 0.8,
                    "pan": 0.0,
                    "name": name,
                    "color": 0x4A5055,
                    "muted": False,
                    "solo": False,
                    "armed": False,
                    "peak": 0.0,
                    "routes": dict.fromkeys(range(127), False),
                }
            )

        # channels state
        self.channels_list: list[dict[str, Any]] = [
            {
                "name": "Sampler",
                "volume": 0.78,
                "pan": 0.0,
                "color": 0x4A5055,
                "muted": False,
                "solo": False,
                "pitch": 0.0,
                "target_fx": 0,
                "step_grid": [0] * 16,
            },
            {
                "name": "3x Osc",
                "volume": 0.78,
                "pan": 0.0,
                "color": 0x4A5055,
                "muted": False,
                "solo": False,
                "pitch": 0.0,
                "target_fx": 0,
                "step_grid": [0] * 16,
            },
            {
                "name": "FL Keys",
                "volume": 0.78,
                "pan": 0.0,
                "color": 0x4A5055,
                "muted": False,
                "solo": False,
                "pitch": 0.0,
                "target_fx": 0,
                "step_grid": [0] * 16,
            },
        ]
        self.channels_selected: int = 0
        self.triggered_notes: list[dict[str, Any]] = []

        # patterns state
        self.patterns_list: list[dict[str, Any]] = [
            {"name": f"Pattern {i}", "color": 0x4A5055, "length": 64} for i in range(1, 17)
        ]
        self.patterns_current: int = 1

        # general state
        self.general_version: int = 44
        self.general_rec_ppq: int = 96
        self.general_undo_history: list[str] = []

        # ui state
        self.ui_version: int = 44
        self.ui_focused: int = 0
        self.ui_windows: dict[int, bool] = {0: True, 1: True, 2: False}
        self.ui_hint: str = ""

        # plugins state: keyed by (track_or_channel_index, slot_index)
        self.plugins_slots: dict[tuple[int, int], dict[str, Any]] = {
            (0, 0): {
                "name": "Fruity Limiter",
                "color": 0x4A5055,
                "presets": ["Default", "Slow Attack", "Punchy"],
                "params": {
                    0: {"name": "Ceiling", "value": 0.9, "text": "0.0 dB"},
                    1: {"name": "Gain", "value": 0.5, "text": "0.0 dB"},
                    2: {"name": "Attack", "value": 0.2, "text": "2.0 ms"},
                    3: {"name": "Release", "value": 0.4, "text": "200 ms"},
                },
            },
            (1, 0): {
                "name": "Fruity Parametric EQ 2",
                "color": 0x4A5055,
                "presets": ["Default", "Warm Vintage"],
                "params": {
                    0: {"name": "Band 1 Gain", "value": 0.5, "text": "0.0 dB"},
                    1: {"name": "Band 1 Freq", "value": 0.3, "text": "100 Hz"},
                    2: {"name": "Band 2 Gain", "value": 0.5, "text": "0.0 dB"},
                },
            },
            (0, -1): {
                "name": "Sampler",
                "color": 0x4A5055,
                "presets": ["Default"],
                "params": {
                    0: {"name": "Pitch", "value": 0.5, "text": "0 cents"},
                },
            },
        }

        # project state
        self.project_title: str = "My Project"
        self.project_author: str = "Producer"
        self.project_comment: str = "Demo Project"
        self.project_dirty: bool = False
        self.project_version_counter: int = 1

        # playlist state: 1-based indexing, 32 tracks
        self.playlist_tracks: list[dict[str, Any]] = [
            {"name": f"Track {i}", "color": 0x4A5055, "muted": False, "solo": False}
            for i in range(1, 33)
        ]
        self.placed_clips: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reset state to defaults."""
        self.__init__()


def create_mock_fl_modules(state: MockFLState) -> dict[str, types.ModuleType]:
    """Create simulated FL Studio modules bound to the provided state."""
    mods: dict[str, types.ModuleType] = {}

    # 1. device module
    mod_dev = types.ModuleType("device")

    def _midiOutSysex(data: Any) -> None:
        if isinstance(data, (bytes, bytearray)):
            state.device_sent_sysex.append(bytes(data))
        else:
            state.device_sent_sysex.append(bytes(list(data)))

    def _isAssigned() -> bool:
        return state.device_assigned

    def _getPortNumber() -> int:
        return state.device_port

    def _getName() -> str:
        return state.device_name

    mod_dev.midiOutSysex = _midiOutSysex  # type: ignore
    mod_dev.isAssigned = _isAssigned  # type: ignore
    mod_dev.getPortNumber = _getPortNumber  # type: ignore
    mod_dev.getName = _getName  # type: ignore
    mods["device"] = mod_dev

    # 2. transport module
    mod_trans = types.ModuleType("transport")

    def _start() -> None:
        state.transport_playing = True

    def _stop() -> None:
        state.transport_playing = False

    def _isPlaying() -> bool:
        return state.transport_playing

    def _record() -> None:
        state.transport_recording = not state.transport_recording

    def _isRecording() -> bool:
        return state.transport_recording

    def _setSongPos(pos: float) -> None:
        state.transport_song_pos = float(pos)

    def _getSongPos(mode: int = 0) -> float:
        return state.transport_song_pos

    def _getSongLength(mode: int = 0) -> float:
        return state.transport_song_length

    def _setLoopMode(mode: Any = -1) -> None:
        if mode is not None and int(mode) >= 0:
            state.transport_loop_mode = int(mode)
        else:
            state.transport_loop_mode = 1 if state.transport_loop_mode == 0 else 0

    def _getLoopMode() -> int:
        return state.transport_loop_mode

    def _getTempo() -> float:
        return state.transport_tempo

    def _setTempo(bpm: float) -> None:
        state.transport_tempo = float(bpm)

    def _getMetronome() -> bool:
        return state.transport_metronome

    def _setMetronome(enabled: Any = None) -> None:
        if enabled is None:
            state.transport_metronome = not state.transport_metronome
        else:
            state.transport_metronome = bool(enabled)

    def _getTimeSignature() -> list[int]:
        return list(state.transport_time_signature)

    def _globalTransport(command: int, value: int = 0) -> int:
        if command == 110:  # FPT_Metronome
            state.transport_metronome = not state.transport_metronome
        elif command == 10:  # FPT_Play
            state.transport_playing = True
        elif command == 11:  # FPT_Stop
            state.transport_playing = False
        elif command == 12:  # FPT_Record
            state.transport_recording = not state.transport_recording
        return 1

    mod_trans.start = _start  # type: ignore
    mod_trans.stop = _stop  # type: ignore
    mod_trans.isPlaying = _isPlaying  # type: ignore
    mod_trans.record = _record  # type: ignore
    mod_trans.isRecording = _isRecording  # type: ignore
    mod_trans.setSongPos = _setSongPos  # type: ignore
    mod_trans.getSongPos = _getSongPos  # type: ignore
    mod_trans.getSongLength = _getSongLength  # type: ignore
    mod_trans.setLoopMode = _setLoopMode  # type: ignore
    mod_trans.getLoopMode = _getLoopMode  # type: ignore
    mod_trans.getTempo = _getTempo  # type: ignore
    mod_trans.setTempo = _setTempo  # type: ignore
    mod_trans.getMetronome = _getMetronome  # type: ignore
    mod_trans.setMetronome = _setMetronome  # type: ignore
    mod_trans.getTimeSignature = _getTimeSignature  # type: ignore
    mod_trans.globalTransport = _globalTransport  # type: ignore
    mods["transport"] = mod_trans

    # 3. mixer module
    mod_mix = types.ModuleType("mixer")

    def _trackCount() -> int:
        return len(state.mixer_tracks)

    def _getTrackVolume(index: int) -> float:
        return state.mixer_tracks[index]["volume"]

    def _setTrackVolume(index: int, volume: float, pickupMode: int = 0) -> None:
        state.mixer_tracks[index]["volume"] = float(volume)

    def _getTrackPan(index: int) -> float:
        return state.mixer_tracks[index]["pan"]

    def _setTrackPan(index: int, pan: float) -> None:
        state.mixer_tracks[index]["pan"] = float(pan)

    def _isTrackMuted(index: int) -> bool:
        return state.mixer_tracks[index]["muted"]

    def _muteTrack(index: int, value: int = -1) -> None:
        if value == -1:
            state.mixer_tracks[index]["muted"] = not state.mixer_tracks[index]["muted"]
        else:
            state.mixer_tracks[index]["muted"] = bool(value)

    def _isTrackSolo(index: int) -> bool:
        return state.mixer_tracks[index]["solo"]

    def _soloTrack(index: int, value: int = -1) -> None:
        if value == -1:
            state.mixer_tracks[index]["solo"] = not state.mixer_tracks[index]["solo"]
        else:
            state.mixer_tracks[index]["solo"] = bool(value)

    def _isTrackArmed(index: int) -> bool:
        return state.mixer_tracks[index].get("armed", False)

    def _armTrack(index: int, value: int = -1) -> None:
        if value == -1:
            state.mixer_tracks[index]["armed"] = not state.mixer_tracks[index].get("armed", False)
        else:
            state.mixer_tracks[index]["armed"] = bool(value)

    def _getTrackName(index: int) -> str:
        return state.mixer_tracks[index]["name"]

    def _setTrackName(index: int, name: str) -> None:
        state.mixer_tracks[index]["name"] = str(name)

    def _getTrackColor(index: int) -> int:
        return state.mixer_tracks[index]["color"]

    def _setTrackColor(index: int, color: int) -> None:
        state.mixer_tracks[index]["color"] = int(color)

    def _getTrackPeaks(index: int, mode: int = 0) -> float:
        return float(state.mixer_tracks[index].get("peak", 0.0))

    def _getRouteTo(source: int, dest: int) -> bool:
        routes = state.mixer_tracks[source].get("routes", {})
        return bool(routes.get(dest, False))

    def _setRouteTo(source: int, dest: int, value: int = 1) -> None:
        routes = state.mixer_tracks[source].setdefault("routes", {})
        routes[dest] = bool(value)

    def _linkTrackToChannel(channel: int, track: int) -> None:
        state.channels_list[channel]["target_fx"] = int(track)

    mod_mix.trackCount = _trackCount  # type: ignore
    mod_mix.getTrackVolume = _getTrackVolume  # type: ignore
    mod_mix.setTrackVolume = _setTrackVolume  # type: ignore
    mod_mix.getTrackPan = _getTrackPan  # type: ignore
    mod_mix.setTrackPan = _setTrackPan  # type: ignore
    mod_mix.isTrackMuted = _isTrackMuted  # type: ignore
    mod_mix.muteTrack = _muteTrack  # type: ignore
    mod_mix.isTrackSolo = _isTrackSolo  # type: ignore
    mod_mix.soloTrack = _soloTrack  # type: ignore
    mod_mix.isTrackArmed = _isTrackArmed  # type: ignore
    mod_mix.armTrack = _armTrack  # type: ignore
    mod_mix.getTrackName = _getTrackName  # type: ignore
    mod_mix.setTrackName = _setTrackName  # type: ignore
    mod_mix.getTrackColor = _getTrackColor  # type: ignore
    mod_mix.setTrackColor = _setTrackColor  # type: ignore
    mod_mix.getTrackPeaks = _getTrackPeaks  # type: ignore
    mod_mix.getRouteTo = _getRouteTo  # type: ignore
    mod_mix.setRouteTo = _setRouteTo  # type: ignore
    mod_mix.linkTrackToChannel = _linkTrackToChannel  # type: ignore
    mods["mixer"] = mod_mix

    # 4. channels module
    mod_chan = types.ModuleType("channels")

    def _channelCount(mode: int = 0) -> int:
        return len(state.channels_list)

    def _getChannelName(index: int) -> str:
        return state.channels_list[index]["name"]

    def _setChannelName(index: int, name: str) -> None:
        state.channels_list[index]["name"] = str(name)

    def _getChannelVolume(index: int) -> float:
        return state.channels_list[index]["volume"]

    def _setChannelVolume(index: int, volume: float) -> None:
        state.channels_list[index]["volume"] = float(volume)

    def _getChannelPan(index: int) -> float:
        return state.channels_list[index]["pan"]

    def _setChannelPan(index: int, pan: float) -> None:
        state.channels_list[index]["pan"] = float(pan)

    def _isChannelMuted(index: int) -> bool:
        return state.channels_list[index]["muted"]

    def _muteChannel(index: int, value: int = -1) -> None:
        if value == -1:
            state.channels_list[index]["muted"] = not state.channels_list[index]["muted"]
        else:
            state.channels_list[index]["muted"] = bool(value)

    def _isChannelSolo(index: int) -> bool:
        return state.channels_list[index]["solo"]

    def _soloChannel(index: int, value: int = -1) -> None:
        if value == -1:
            state.channels_list[index]["solo"] = not state.channels_list[index]["solo"]
        else:
            state.channels_list[index]["solo"] = bool(value)

    def _getChannelColor(index: int) -> int:
        return state.channels_list[index]["color"]

    def _setChannelColor(index: int, color: int) -> None:
        state.channels_list[index]["color"] = int(color)

    def _getChannelPitch(index: int) -> float:
        return float(state.channels_list[index].get("pitch", 0.0))

    def _setChannelPitch(index: int, pitch: float) -> None:
        state.channels_list[index]["pitch"] = float(pitch)

    def _getTargetFxTrack(index: int) -> int:
        return int(state.channels_list[index].get("target_fx", 0))

    def _setTargetFxTrack(index: int, track: int) -> None:
        state.channels_list[index]["target_fx"] = int(track)

    def _triggerNote(index: int, note: int = 60, velocity: int = 100, duration: int = 1) -> None:
        state.triggered_notes.append(
            {
                "channel": index,
                "note": int(note),
                "velocity": int(velocity),
                "duration": int(duration),
            }
        )

    def _getStepGrid(index: int) -> list[int]:
        return list(state.channels_list[index].get("step_grid", [0] * 16))

    def _setStepGrid(index: int, steps: list[Any]) -> None:
        state.channels_list[index]["step_grid"] = [int(bool(s)) for s in steps]

    def _selectedChannel() -> int:
        return state.channels_selected

    def _selectChannel(index: int, value: int = 1) -> None:
        state.channels_selected = int(index)

    mod_chan.channelCount = _channelCount  # type: ignore
    mod_chan.getChannelName = _getChannelName  # type: ignore
    mod_chan.setChannelName = _setChannelName  # type: ignore
    mod_chan.getChannelVolume = _getChannelVolume  # type: ignore
    mod_chan.setChannelVolume = _setChannelVolume  # type: ignore
    mod_chan.getChannelPan = _getChannelPan  # type: ignore
    mod_chan.setChannelPan = _setChannelPan  # type: ignore
    mod_chan.isChannelMuted = _isChannelMuted  # type: ignore
    mod_chan.muteChannel = _muteChannel  # type: ignore
    mod_chan.isChannelSolo = _isChannelSolo  # type: ignore
    mod_chan.soloChannel = _soloChannel  # type: ignore
    mod_chan.getChannelColor = _getChannelColor  # type: ignore
    mod_chan.setChannelColor = _setChannelColor  # type: ignore
    mod_chan.getChannelPitch = _getChannelPitch  # type: ignore
    mod_chan.setChannelPitch = _setChannelPitch  # type: ignore
    mod_chan.getTargetFxTrack = _getTargetFxTrack  # type: ignore
    mod_chan.setTargetFxTrack = _setTargetFxTrack  # type: ignore
    mod_chan.triggerNote = _triggerNote  # type: ignore
    mod_chan.getStepGrid = _getStepGrid  # type: ignore
    mod_chan.setStepGrid = _setStepGrid  # type: ignore
    mod_chan.selectedChannel = _selectedChannel  # type: ignore
    mod_chan.selectChannel = _selectChannel  # type: ignore
    mods["channels"] = mod_chan

    # 5. patterns module
    mod_pat = types.ModuleType("patterns")

    def _patternCount() -> int:
        return len(state.patterns_list)

    def _patternNumber() -> int:
        return state.patterns_current

    def _getPatternName(index: int) -> str:
        return state.patterns_list[index - 1]["name"]

    def _setPatternName(index: int, name: str) -> None:
        state.patterns_list[index - 1]["name"] = str(name)

    def _getPatternColor(index: int) -> int:
        return state.patterns_list[index - 1]["color"]

    def _setPatternColor(index: int, color: int) -> None:
        state.patterns_list[index - 1]["color"] = int(color)

    def _getPatternLength(index: int) -> int:
        return state.patterns_list[index - 1]["length"]

    def _setPatternLength(index: int, length: int) -> None:
        state.patterns_list[index - 1]["length"] = int(length)

    def _jumpToPattern(index: int) -> None:
        state.patterns_current = int(index)

    def _selectPattern(index: int, value: int = 1) -> None:
        state.patterns_current = int(index)

    def _clearPattern(index: int) -> None:
        state.patterns_list[index - 1]["name"] = f"Pattern {index}"
        state.patterns_list[index - 1]["length"] = 64

    mod_pat.patternCount = _patternCount  # type: ignore
    mod_pat.patternNumber = _patternNumber  # type: ignore
    mod_pat.getPatternName = _getPatternName  # type: ignore
    mod_pat.setPatternName = _setPatternName  # type: ignore
    mod_pat.getPatternColor = _getPatternColor  # type: ignore
    mod_pat.setPatternColor = _setPatternColor  # type: ignore
    mod_pat.getPatternLength = _getPatternLength  # type: ignore
    mod_pat.setPatternLength = _setPatternLength  # type: ignore
    mod_pat.jumpToPattern = _jumpToPattern  # type: ignore
    mod_pat.selectPattern = _selectPattern  # type: ignore
    mod_pat.clearPattern = _clearPattern  # type: ignore
    mods["patterns"] = mod_pat

    # 6. general module
    mod_gen = types.ModuleType("general")

    def _getVersion() -> int:
        return state.general_version

    def _getRecPPQ() -> int:
        return state.general_rec_ppq

    def _saveUndo(name: str, flags: int = 0) -> None:
        state.general_undo_history.append(str(name))

    def _undo() -> None:
        pass

    def _redo() -> None:
        pass

    def _undoUp() -> None:
        pass

    def _getChangedFlag() -> int:
        return 1 if state.project_dirty else 0

    def _clearChangedFlag() -> None:
        state.project_dirty = False

    mod_gen.getVersion = _getVersion  # type: ignore
    mod_gen.getRecPPQ = _getRecPPQ  # type: ignore
    mod_gen.saveUndo = _saveUndo  # type: ignore
    mod_gen.undo = _undo  # type: ignore
    mod_gen.redo = _redo  # type: ignore
    mod_gen.undoUp = _undoUp  # type: ignore
    mod_gen.getChangedFlag = _getChangedFlag  # type: ignore
    mod_gen.clearChangedFlag = _clearChangedFlag  # type: ignore
    mods["general"] = mod_gen

    # 7. ui module
    mod_ui = types.ModuleType("ui")

    def _ui_getVersion() -> int:
        return state.ui_version

    def _getFocused(window: int) -> bool:
        return state.ui_focused == window

    def _setFocused(window: int) -> None:
        state.ui_focused = int(window)

    def _showWindow(window: int) -> None:
        state.ui_windows[window] = True

    def _hideWindow(window: int) -> None:
        state.ui_windows[window] = False

    def _getVisible(window: int) -> bool:
        return state.ui_windows.get(window, False)

    def _setHintMsg(msg: str) -> None:
        state.ui_hint = str(msg)

    mod_ui.getVersion = _ui_getVersion  # type: ignore
    mod_ui.getFocused = _getFocused  # type: ignore
    mod_ui.setFocused = _setFocused  # type: ignore
    mod_ui.showWindow = _showWindow  # type: ignore
    mod_ui.hideWindow = _hideWindow  # type: ignore
    mod_ui.getVisible = _getVisible  # type: ignore
    mod_ui.setHintMsg = _setHintMsg  # type: ignore
    mods["ui"] = mod_ui

    # 8. plugins module
    mod_plug = types.ModuleType("plugins")

    def _isValid(index: int, slot: int = -1) -> bool:
        return (int(index), int(slot)) in state.plugins_slots

    def _getPluginName(index: int, slot: int = -1) -> str:
        return state.plugins_slots.get((int(index), int(slot)), {}).get("name", "")

    def _plug_getName(index: int, slot: int = -1) -> str:
        return state.plugins_slots.get((int(index), int(slot)), {}).get("name", "")

    def _getColor(index: int, slot: int = -1) -> int:
        return state.plugins_slots.get((int(index), int(slot)), {}).get("color", 0)

    def _getColorName(index: int, slot: int = -1) -> str:
        return "Default"

    def _getParamCount(index: int, slot: int = -1) -> int:
        return len(state.plugins_slots.get((int(index), int(slot)), {}).get("params", {}))

    def _getParamName(paramIndex: int, index: int, slot: int = -1) -> str:
        params = state.plugins_slots.get((int(index), int(slot)), {}).get("params", {})
        return params.get(int(paramIndex), {}).get("name", f"Param {paramIndex}")

    def _getParamValue(paramIndex: int, index: int, slot: int = -1) -> float:
        params = state.plugins_slots.get((int(index), int(slot)), {}).get("params", {})
        return float(params.get(int(paramIndex), {}).get("value", 0.0))

    def _getParamValueText(paramIndex: int, index: int, slot: int = -1) -> str:
        params = state.plugins_slots.get((int(index), int(slot)), {}).get("params", {})
        param = params.get(int(paramIndex), {})
        return str(param.get("text", f"{float(param.get('value', 0.0)):.2f}"))

    def _setParamValue(value: float, paramIndex: int, index: int, slot: int = -1) -> None:
        key = (int(index), int(slot))
        plugin = state.plugins_slots.setdefault(
            key,
            {"name": "Plugin", "color": 0, "presets": [], "params": {}},
        )
        param = plugin["params"].setdefault(
            int(paramIndex),
            {"name": f"Param {paramIndex}", "value": 0.0, "text": ""},
        )
        param["value"] = float(value)
        param["text"] = f"{float(value):.2f}"

    def _getPresetCount(index: int, slot: int = -1) -> int:
        return len(state.plugins_slots.get((int(index), int(slot)), {}).get("presets", []))

    def _getPresetName(presetIndex: int, index: int, slot: int = -1) -> str:
        presets = state.plugins_slots.get((int(index), int(slot)), {}).get("presets", [])
        p_idx = int(presetIndex)
        return presets[p_idx] if 0 <= p_idx < len(presets) else ""

    def _showEditor(index: int, slot: int = -1) -> None:
        pass

    mod_plug.isValid = _isValid  # type: ignore
    mod_plug.getPluginName = _getPluginName  # type: ignore
    mod_plug.getName = _plug_getName  # type: ignore
    mod_plug.getColor = _getColor  # type: ignore
    mod_plug.getColorName = _getColorName  # type: ignore
    mod_plug.getParamCount = _getParamCount  # type: ignore
    mod_plug.getParamName = _getParamName  # type: ignore
    mod_plug.getParamValue = _getParamValue  # type: ignore
    mod_plug.getParamValueText = _getParamValueText  # type: ignore
    mod_plug.setParamValue = _setParamValue  # type: ignore
    mod_plug.getPresetCount = _getPresetCount  # type: ignore
    mod_plug.getPresetName = _getPresetName  # type: ignore
    mod_plug.showEditor = _showEditor  # type: ignore
    mods["plugins"] = mod_plug

    # 9. project module
    mod_proj = types.ModuleType("project")

    def _getTitle() -> str:
        return state.project_title

    def _getAuthor() -> str:
        return state.project_author

    def _getComment() -> str:
        return state.project_comment

    def _isDirty() -> bool:
        return state.project_dirty

    def _save() -> None:
        state.project_dirty = False

    def _saveNewVersion() -> None:
        state.project_version_counter += 1
        state.project_dirty = False

    mod_proj.getTitle = _getTitle  # type: ignore
    mod_proj.getAuthor = _getAuthor  # type: ignore
    mod_proj.getComment = _getComment  # type: ignore
    mod_proj.isDirty = _isDirty  # type: ignore
    mod_proj.save = _save  # type: ignore
    mod_proj.saveNewVersion = _saveNewVersion  # type: ignore
    mods["project"] = mod_proj

    # 10. playlist module
    mod_play = types.ModuleType("playlist")

    def _playlist_trackCount() -> int:
        return len(state.playlist_tracks)

    def _playlist_getTrackName(index: int) -> str:
        return state.playlist_tracks[int(index) - 1]["name"]

    def _playlist_setTrackName(index: int, name: str) -> None:
        state.playlist_tracks[int(index) - 1]["name"] = str(name)

    def _playlist_getTrackColor(index: int) -> int:
        return state.playlist_tracks[int(index) - 1]["color"]

    def _playlist_setTrackColor(index: int, color: int) -> None:
        state.playlist_tracks[int(index) - 1]["color"] = int(color)

    def _playlist_isTrackMuted(index: int) -> bool:
        return state.playlist_tracks[int(index) - 1]["muted"]

    def _playlist_muteTrack(index: int, value: int = -1) -> None:
        idx = int(index) - 1
        if value == -1:
            state.playlist_tracks[idx]["muted"] = not state.playlist_tracks[idx]["muted"]
        else:
            state.playlist_tracks[idx]["muted"] = bool(value)

    def _playlist_isTrackSolo(index: int) -> bool:
        return state.playlist_tracks[int(index) - 1]["solo"]

    def _playlist_soloTrack(index: int, value: int = -1) -> None:
        idx = int(index) - 1
        if value == -1:
            state.playlist_tracks[idx]["solo"] = not state.playlist_tracks[idx]["solo"]
        else:
            state.playlist_tracks[idx]["solo"] = bool(value)

    def _playlist_placePattern(pattern: int, track: int, time: float = 0.0) -> None:
        state.placed_clips.append(
            {"pattern": int(pattern), "track": int(track), "time": float(time)}
        )

    mod_play.trackCount = _playlist_trackCount  # type: ignore
    mod_play.getTrackName = _playlist_getTrackName  # type: ignore
    mod_play.setTrackName = _playlist_setTrackName  # type: ignore
    mod_play.getTrackColor = _playlist_getTrackColor  # type: ignore
    mod_play.setTrackColor = _playlist_setTrackColor  # type: ignore
    mod_play.isTrackMuted = _playlist_isTrackMuted  # type: ignore
    mod_play.muteTrack = _playlist_muteTrack  # type: ignore
    mod_play.isTrackSolo = _playlist_isTrackSolo  # type: ignore
    mod_play.soloTrack = _playlist_soloTrack  # type: ignore
    mod_play.placePattern = _playlist_placePattern  # type: ignore
    mods["playlist"] = mod_play

    return mods
