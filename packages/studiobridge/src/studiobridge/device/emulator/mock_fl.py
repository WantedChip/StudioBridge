"""Mock FL Studio builtins and API modules with realistic state.

Provides simulated FL Studio embedded environment and sandbox audit hooks / import blockers
restricting forbidden modules per [DEV-30] and 05_l0c_device_script_manifest.md §1, §9.
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
            },
            {
                "name": "3x Osc",
                "volume": 0.78,
                "pan": 0.0,
                "color": 0x4A5055,
                "muted": False,
                "solo": False,
            },
            {
                "name": "FL Keys",
                "volume": 0.78,
                "pan": 0.0,
                "color": 0x4A5055,
                "muted": False,
                "solo": False,
            },
        ]
        self.channels_selected: int = 0

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

    def _setLoopMode() -> None:
        state.transport_loop_mode = 1 if state.transport_loop_mode == 0 else 0

    def _getLoopMode() -> int:
        return state.transport_loop_mode

    def _globalTransport(command: int, value: int = 0) -> int:
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

    def _getTrackName(index: int) -> str:
        return state.mixer_tracks[index]["name"]

    def _setTrackName(index: int, name: str) -> None:
        state.mixer_tracks[index]["name"] = str(name)

    def _getTrackColor(index: int) -> int:
        return state.mixer_tracks[index]["color"]

    def _setTrackColor(index: int, color: int) -> None:
        state.mixer_tracks[index]["color"] = int(color)

    mod_mix.trackCount = _trackCount  # type: ignore
    mod_mix.getTrackVolume = _getTrackVolume  # type: ignore
    mod_mix.setTrackVolume = _setTrackVolume  # type: ignore
    mod_mix.getTrackPan = _getTrackPan  # type: ignore
    mod_mix.setTrackPan = _setTrackPan  # type: ignore
    mod_mix.isTrackMuted = _isTrackMuted  # type: ignore
    mod_mix.muteTrack = _muteTrack  # type: ignore
    mod_mix.isTrackSolo = _isTrackSolo  # type: ignore
    mod_mix.soloTrack = _soloTrack  # type: ignore
    mod_mix.getTrackName = _getTrackName  # type: ignore
    mod_mix.setTrackName = _setTrackName  # type: ignore
    mod_mix.getTrackColor = _getTrackColor  # type: ignore
    mod_mix.setTrackColor = _setTrackColor  # type: ignore
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

    def _jumpToPattern(index: int) -> None:
        state.patterns_current = int(index)

    mod_pat.patternCount = _patternCount  # type: ignore
    mod_pat.patternNumber = _patternNumber  # type: ignore
    mod_pat.getPatternName = _getPatternName  # type: ignore
    mod_pat.setPatternName = _setPatternName  # type: ignore
    mod_pat.getPatternColor = _getPatternColor  # type: ignore
    mod_pat.setPatternColor = _setPatternColor  # type: ignore
    mod_pat.getPatternLength = _getPatternLength  # type: ignore
    mod_pat.jumpToPattern = _jumpToPattern  # type: ignore
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

    mod_gen.getVersion = _getVersion  # type: ignore
    mod_gen.getRecPPQ = _getRecPPQ  # type: ignore
    mod_gen.saveUndo = _saveUndo  # type: ignore
    mod_gen.undo = _undo  # type: ignore
    mod_gen.redo = _redo  # type: ignore
    mod_gen.undoUp = _undoUp  # type: ignore
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

    mod_ui.getVersion = _ui_getVersion  # type: ignore
    mod_ui.getFocused = _getFocused  # type: ignore
    mod_ui.setFocused = _setFocused  # type: ignore
    mod_ui.showWindow = _showWindow  # type: ignore
    mod_ui.hideWindow = _hideWindow  # type: ignore
    mod_ui.getVisible = _getVisible  # type: ignore
    mods["ui"] = mod_ui

    return mods
