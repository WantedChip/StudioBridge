"""Emulator module stubs generated from FL Studio API manifest.

Provides default no-op stub implementations for all manifest functions.
Isolated from higher layers per [DEV-30].
"""

from __future__ import annotations

import types
from typing import Any


def _default_stub(*args: Any, **kwargs: Any) -> Any:
    return None


def create_manifest_stubs() -> dict[str, types.ModuleType]:
    """Create a dictionary of all manifest module stubs."""
    stubs: dict[str, types.ModuleType] = {}

    # Module: channels
    mod_channels = types.ModuleType("channels")

    def _channels_channelCount(mode: Any = None) -> Any:
        return 0

    mod_channels.channelCount = _channels_channelCount  # type: ignore

    def _channels_channelNumber(index: Any = None) -> Any:
        return 0

    mod_channels.channelNumber = _channels_channelNumber  # type: ignore

    def _channels_getChannelColor(index: Any = None) -> Any:
        return 0

    mod_channels.getChannelColor = _channels_getChannelColor  # type: ignore

    def _channels_getChannelName(index: Any = None) -> Any:
        return ""

    mod_channels.getChannelName = _channels_getChannelName  # type: ignore

    def _channels_getChannelPan(index: Any = None) -> Any:
        return 0.0

    mod_channels.getChannelPan = _channels_getChannelPan  # type: ignore

    def _channels_getChannelPitch(index: Any = None) -> Any:
        return 0.0

    mod_channels.getChannelPitch = _channels_getChannelPitch  # type: ignore

    def _channels_getChannelVolume(index: Any = None) -> Any:
        return 0.0

    mod_channels.getChannelVolume = _channels_getChannelVolume  # type: ignore

    def _channels_getTargetFxTrack(index: Any = None) -> Any:
        return 0

    mod_channels.getTargetFxTrack = _channels_getTargetFxTrack  # type: ignore

    def _channels_incEventValue(eventId: Any = None, value: Any = None, step: Any = None) -> Any:
        return None

    mod_channels.incEventValue = _channels_incEventValue  # type: ignore

    def _channels_isChannelMuted(index: Any = None) -> Any:
        return False

    mod_channels.isChannelMuted = _channels_isChannelMuted  # type: ignore

    def _channels_isChannelSolo(index: Any = None) -> Any:
        return False

    mod_channels.isChannelSolo = _channels_isChannelSolo  # type: ignore

    def _channels_muteChannel(index: Any = None, value: Any = None) -> Any:
        return None

    mod_channels.muteChannel = _channels_muteChannel  # type: ignore

    def _channels_selectChannel(index: Any = None, value: Any = None) -> Any:
        return None

    mod_channels.selectChannel = _channels_selectChannel  # type: ignore

    def _channels_selectedChannel() -> Any:
        return 0

    mod_channels.selectedChannel = _channels_selectedChannel  # type: ignore

    def _channels_setChannelColor(index: Any = None, color: Any = None) -> Any:
        return None

    mod_channels.setChannelColor = _channels_setChannelColor  # type: ignore

    def _channels_setChannelName(index: Any = None, name: Any = None) -> Any:
        return None

    mod_channels.setChannelName = _channels_setChannelName  # type: ignore

    def _channels_setChannelPan(index: Any = None, pan: Any = None) -> Any:
        return None

    mod_channels.setChannelPan = _channels_setChannelPan  # type: ignore

    def _channels_setChannelPitch(index: Any = None, pitch: Any = None) -> Any:
        return None

    mod_channels.setChannelPitch = _channels_setChannelPitch  # type: ignore

    def _channels_setChannelVolume(index: Any = None, volume: Any = None) -> Any:
        return None

    mod_channels.setChannelVolume = _channels_setChannelVolume  # type: ignore

    def _channels_setTargetFxTrack(index: Any = None, track: Any = None) -> Any:
        return None

    mod_channels.setTargetFxTrack = _channels_setTargetFxTrack  # type: ignore

    def _channels_soloChannel(index: Any = None, value: Any = None) -> Any:
        return None

    mod_channels.soloChannel = _channels_soloChannel  # type: ignore
    stubs["channels"] = mod_channels

    # Module: device
    mod_device = types.ModuleType("device")

    def _device_baseTrackSelect(offset: Any = None, step: Any = None) -> Any:
        return None

    mod_device.baseTrackSelect = _device_baseTrackSelect  # type: ignore

    def _device_dispatch(messageId: Any = None, value: Any = None) -> Any:
        return None

    mod_device.dispatch = _device_dispatch  # type: ignore

    def _device_forwardMIDICC(status: Any = None, data1: Any = None, data2: Any = None) -> Any:
        return None

    mod_device.forwardMIDICC = _device_forwardMIDICC  # type: ignore

    def _device_getName() -> Any:
        return ""

    mod_device.getName = _device_getName  # type: ignore

    def _device_getPortNumber() -> Any:
        return 0

    mod_device.getPortNumber = _device_getPortNumber  # type: ignore

    def _device_isAssigned() -> Any:
        return False

    mod_device.isAssigned = _device_isAssigned  # type: ignore

    def _device_midiOutMsg(message: Any = None) -> Any:
        return None

    mod_device.midiOutMsg = _device_midiOutMsg  # type: ignore

    def _device_midiOutSysex(data: Any = None) -> Any:
        return None

    mod_device.midiOutSysex = _device_midiOutSysex  # type: ignore

    def _device_processMIDICC(event: Any = None) -> Any:
        return 0

    mod_device.processMIDICC = _device_processMIDICC  # type: ignore
    stubs["device"] = mod_device

    # Module: general
    mod_general = types.ModuleType("general")

    def _general_clearChangedFlag() -> Any:
        return None

    mod_general.clearChangedFlag = _general_clearChangedFlag  # type: ignore

    def _general_getChangedFlag() -> Any:
        return 0

    mod_general.getChangedFlag = _general_getChangedFlag  # type: ignore

    def _general_getRecPPQ() -> Any:
        return 0

    mod_general.getRecPPQ = _general_getRecPPQ  # type: ignore

    def _general_getVersion() -> Any:
        return 0

    mod_general.getVersion = _general_getVersion  # type: ignore

    def _general_processRECEvent(eventId: Any = None, value: Any = None, flags: Any = None) -> Any:
        return 0

    mod_general.processRECEvent = _general_processRECEvent  # type: ignore

    def _general_redo() -> Any:
        return None

    mod_general.redo = _general_redo  # type: ignore

    def _general_restore() -> Any:
        return None

    mod_general.restore = _general_restore  # type: ignore

    def _general_saveUndo(name: Any = None, flags: Any = None) -> Any:
        return None

    mod_general.saveUndo = _general_saveUndo  # type: ignore

    def _general_undo() -> Any:
        return None

    mod_general.undo = _general_undo  # type: ignore

    def _general_undoUp() -> Any:
        return None

    mod_general.undoUp = _general_undoUp  # type: ignore
    stubs["general"] = mod_general

    # Module: mixer
    mod_mixer = types.ModuleType("mixer")

    def _mixer_armTrack(index: Any = None, value: Any = None) -> Any:
        return None

    mod_mixer.armTrack = _mixer_armTrack  # type: ignore

    def _mixer_enableTrack(index: Any = None, value: Any = None) -> Any:
        return None

    mod_mixer.enableTrack = _mixer_enableTrack  # type: ignore

    def _mixer_enableTrackSlots(index: Any = None, value: Any = None) -> Any:
        return None

    mod_mixer.enableTrackSlots = _mixer_enableTrackSlots  # type: ignore

    def _mixer_getSongStepPos() -> Any:
        return 0

    mod_mixer.getSongStepPos = _mixer_getSongStepPos  # type: ignore

    def _mixer_getTrackColor(index: Any = None) -> Any:
        return 0

    mod_mixer.getTrackColor = _mixer_getTrackColor  # type: ignore

    def _mixer_getTrackName(index: Any = None) -> Any:
        return ""

    mod_mixer.getTrackName = _mixer_getTrackName  # type: ignore

    def _mixer_getTrackNumber(index: Any = None) -> Any:
        return 0

    mod_mixer.getTrackNumber = _mixer_getTrackNumber  # type: ignore

    def _mixer_getTrackPan(index: Any = None) -> Any:
        return 0.0

    mod_mixer.getTrackPan = _mixer_getTrackPan  # type: ignore

    def _mixer_getTrackSlotsEnabled(index: Any = None) -> Any:
        return False

    mod_mixer.getTrackSlotsEnabled = _mixer_getTrackSlotsEnabled  # type: ignore

    def _mixer_getTrackVolume(index: Any = None) -> Any:
        return 0.0

    mod_mixer.getTrackVolume = _mixer_getTrackVolume  # type: ignore

    def _mixer_isTrackArmed(index: Any = None) -> Any:
        return False

    mod_mixer.isTrackArmed = _mixer_isTrackArmed  # type: ignore

    def _mixer_isTrackEnabled(index: Any = None) -> Any:
        return False

    mod_mixer.isTrackEnabled = _mixer_isTrackEnabled  # type: ignore

    def _mixer_isTrackMuted(index: Any = None) -> Any:
        return False

    mod_mixer.isTrackMuted = _mixer_isTrackMuted  # type: ignore

    def _mixer_isTrackSolo(index: Any = None) -> Any:
        return False

    mod_mixer.isTrackSolo = _mixer_isTrackSolo  # type: ignore

    def _mixer_linkTrackToChannel(mode: Any = None) -> Any:
        return None

    mod_mixer.linkTrackToChannel = _mixer_linkTrackToChannel  # type: ignore

    def _mixer_muteTrack(index: Any = None, value: Any = None) -> Any:
        return None

    mod_mixer.muteTrack = _mixer_muteTrack  # type: ignore

    def _mixer_setTrackColor(index: Any = None, color: Any = None) -> Any:
        return None

    mod_mixer.setTrackColor = _mixer_setTrackColor  # type: ignore

    def _mixer_setTrackName(index: Any = None, name: Any = None) -> Any:
        return None

    mod_mixer.setTrackName = _mixer_setTrackName  # type: ignore

    def _mixer_setTrackNumber(index: Any = None, number: Any = None) -> Any:
        return None

    mod_mixer.setTrackNumber = _mixer_setTrackNumber  # type: ignore

    def _mixer_setTrackPan(index: Any = None, pan: Any = None) -> Any:
        return None

    mod_mixer.setTrackPan = _mixer_setTrackPan  # type: ignore

    def _mixer_setTrackVolume(index: Any = None, volume: Any = None, pickupMode: Any = None) -> Any:
        return None

    mod_mixer.setTrackVolume = _mixer_setTrackVolume  # type: ignore

    def _mixer_soloTrack(index: Any = None, value: Any = None) -> Any:
        return None

    mod_mixer.soloTrack = _mixer_soloTrack  # type: ignore

    def _mixer_trackCount() -> Any:
        return 0

    mod_mixer.trackCount = _mixer_trackCount  # type: ignore
    stubs["mixer"] = mod_mixer

    # Module: patterns
    mod_patterns = types.ModuleType("patterns")

    def _patterns_ensureValidPattern(index: Any = None) -> Any:
        return None

    mod_patterns.ensureValidPattern = _patterns_ensureValidPattern  # type: ignore

    def _patterns_getPatternColor(index: Any = None) -> Any:
        return 0

    mod_patterns.getPatternColor = _patterns_getPatternColor  # type: ignore

    def _patterns_getPatternLength(index: Any = None) -> Any:
        return 0

    mod_patterns.getPatternLength = _patterns_getPatternLength  # type: ignore

    def _patterns_getPatternName(index: Any = None) -> Any:
        return ""

    mod_patterns.getPatternName = _patterns_getPatternName  # type: ignore

    def _patterns_isPatternSelected(index: Any = None) -> Any:
        return False

    mod_patterns.isPatternSelected = _patterns_isPatternSelected  # type: ignore

    def _patterns_jumpToPattern(index: Any = None) -> Any:
        return None

    mod_patterns.jumpToPattern = _patterns_jumpToPattern  # type: ignore

    def _patterns_patternCount() -> Any:
        return 0

    mod_patterns.patternCount = _patterns_patternCount  # type: ignore

    def _patterns_patternNumber() -> Any:
        return 0

    mod_patterns.patternNumber = _patterns_patternNumber  # type: ignore

    def _patterns_selectPattern(index: Any = None, value: Any = None) -> Any:
        return None

    mod_patterns.selectPattern = _patterns_selectPattern  # type: ignore

    def _patterns_setPatternColor(index: Any = None, color: Any = None) -> Any:
        return None

    mod_patterns.setPatternColor = _patterns_setPatternColor  # type: ignore

    def _patterns_setPatternLength(index: Any = None, length: Any = None) -> Any:
        return None

    mod_patterns.setPatternLength = _patterns_setPatternLength  # type: ignore

    def _patterns_setPatternName(index: Any = None, name: Any = None) -> Any:
        return None

    mod_patterns.setPatternName = _patterns_setPatternName  # type: ignore
    stubs["patterns"] = mod_patterns

    # Module: plugins
    mod_plugins = types.ModuleType("plugins")

    def _plugins_getColor(index: Any = None, slot: Any = None) -> Any:
        return 0

    mod_plugins.getColor = _plugins_getColor  # type: ignore

    def _plugins_getColorName(index: Any = None, slot: Any = None) -> Any:
        return ""

    mod_plugins.getColorName = _plugins_getColorName  # type: ignore

    def _plugins_getName(index: Any = None, slot: Any = None) -> Any:
        return ""

    mod_plugins.getName = _plugins_getName  # type: ignore

    def _plugins_getParamCount(index: Any = None, slot: Any = None) -> Any:
        return 0

    mod_plugins.getParamCount = _plugins_getParamCount  # type: ignore

    def _plugins_getParamName(paramIndex: Any = None, index: Any = None, slot: Any = None) -> Any:
        return ""

    mod_plugins.getParamName = _plugins_getParamName  # type: ignore

    def _plugins_getParamValue(paramIndex: Any = None, index: Any = None, slot: Any = None) -> Any:
        return 0.0

    mod_plugins.getParamValue = _plugins_getParamValue  # type: ignore

    def _plugins_getPluginName(index: Any = None, slot: Any = None) -> Any:
        return ""

    mod_plugins.getPluginName = _plugins_getPluginName  # type: ignore

    def _plugins_getPresetCount(index: Any = None, slot: Any = None) -> Any:
        return 0

    mod_plugins.getPresetCount = _plugins_getPresetCount  # type: ignore

    def _plugins_getPresetName(presetIndex: Any = None, index: Any = None, slot: Any = None) -> Any:
        return ""

    mod_plugins.getPresetName = _plugins_getPresetName  # type: ignore

    def _plugins_isValid(index: Any = None, slot: Any = None) -> Any:
        return False

    mod_plugins.isValid = _plugins_isValid  # type: ignore

    def _plugins_setParamValue(
        value: Any = None, paramIndex: Any = None, index: Any = None, slot: Any = None
    ) -> Any:
        return None

    mod_plugins.setParamValue = _plugins_setParamValue  # type: ignore

    def _plugins_showEditor(index: Any = None, slot: Any = None) -> Any:
        return None

    mod_plugins.showEditor = _plugins_showEditor  # type: ignore
    stubs["plugins"] = mod_plugins

    # Module: transport
    mod_transport = types.ModuleType("transport")

    def _transport_continuousMove(value: Any = None, step: Any = None) -> Any:
        return None

    mod_transport.continuousMove = _transport_continuousMove  # type: ignore

    def _transport_fastForward(value: Any = None, step: Any = None) -> Any:
        return None

    mod_transport.fastForward = _transport_fastForward  # type: ignore

    def _transport_getLoopMode() -> Any:
        return 0

    mod_transport.getLoopMode = _transport_getLoopMode  # type: ignore

    def _transport_getPlaybackSpeed() -> Any:
        return 0.0

    mod_transport.getPlaybackSpeed = _transport_getPlaybackSpeed  # type: ignore

    def _transport_getSongLength(mode: Any = None) -> Any:
        return 0.0

    mod_transport.getSongLength = _transport_getSongLength  # type: ignore

    def _transport_getSongPos(mode: Any = None) -> Any:
        return 0.0

    mod_transport.getSongPos = _transport_getSongPos  # type: ignore

    def _transport_globalTransport(command: Any = None, value: Any = None) -> Any:
        return 0

    mod_transport.globalTransport = _transport_globalTransport  # type: ignore

    def _transport_isPlaying() -> Any:
        return False

    mod_transport.isPlaying = _transport_isPlaying  # type: ignore

    def _transport_isRecording() -> Any:
        return False

    mod_transport.isRecording = _transport_isRecording  # type: ignore

    def _transport_markerJump(step: Any = None, select: Any = None) -> Any:
        return None

    mod_transport.markerJump = _transport_markerJump  # type: ignore

    def _transport_record() -> Any:
        return None

    mod_transport.record = _transport_record  # type: ignore

    def _transport_rewind(value: Any = None, step: Any = None) -> Any:
        return None

    mod_transport.rewind = _transport_rewind  # type: ignore

    def _transport_setLoopMode() -> Any:
        return None

    mod_transport.setLoopMode = _transport_setLoopMode  # type: ignore

    def _transport_setPlaybackSpeed(speed: Any = None) -> Any:
        return None

    mod_transport.setPlaybackSpeed = _transport_setPlaybackSpeed  # type: ignore

    def _transport_setSongPos(pos: Any = None) -> Any:
        return None

    mod_transport.setSongPos = _transport_setSongPos  # type: ignore

    def _transport_start() -> Any:
        return None

    mod_transport.start = _transport_start  # type: ignore

    def _transport_stop() -> Any:
        return None

    mod_transport.stop = _transport_stop  # type: ignore
    stubs["transport"] = mod_transport

    # Module: ui
    mod_ui = types.ModuleType("ui")

    def _ui_crDisplay(index: Any = None, value: Any = None, mode: Any = None) -> Any:
        return None

    mod_ui.crDisplay = _ui_crDisplay  # type: ignore

    def _ui_getFocused(window: Any = None) -> Any:
        return False

    mod_ui.getFocused = _ui_getFocused  # type: ignore

    def _ui_getStepEditMode() -> Any:
        return 0

    mod_ui.getStepEditMode = _ui_getStepEditMode  # type: ignore

    def _ui_getVersion() -> Any:
        return 0

    mod_ui.getVersion = _ui_getVersion  # type: ignore

    def _ui_getVisible(window: Any = None) -> Any:
        return False

    mod_ui.getVisible = _ui_getVisible  # type: ignore

    def _ui_getVisibleForm(formId: Any = None) -> Any:
        return False

    mod_ui.getVisibleForm = _ui_getVisibleForm  # type: ignore

    def _ui_hideWindow(window: Any = None) -> Any:
        return None

    mod_ui.hideWindow = _ui_hideWindow  # type: ignore

    def _ui_jog(value: Any = None) -> Any:
        return None

    mod_ui.jog = _ui_jog  # type: ignore

    def _ui_scrollWindow(window: Any = None, delta: Any = None) -> Any:
        return None

    mod_ui.scrollWindow = _ui_scrollWindow  # type: ignore

    def _ui_setFocused(window: Any = None) -> Any:
        return None

    mod_ui.setFocused = _ui_setFocused  # type: ignore

    def _ui_setFocusedForm(formId: Any = None) -> Any:
        return None

    mod_ui.setFocusedForm = _ui_setFocusedForm  # type: ignore

    def _ui_setStepEditMode(mode: Any = None) -> Any:
        return None

    mod_ui.setStepEditMode = _ui_setStepEditMode  # type: ignore

    def _ui_showWindow(window: Any = None) -> Any:
        return None

    mod_ui.showWindow = _ui_showWindow  # type: ignore

    def _ui_snapMode() -> Any:
        return 0

    mod_ui.snapMode = _ui_snapMode  # type: ignore

    def _ui_snapWindow(window: Any = None, mode: Any = None) -> Any:
        return None

    mod_ui.snapWindow = _ui_snapWindow  # type: ignore
    stubs["ui"] = mod_ui

    return stubs


STUB_MODULES: dict[str, types.ModuleType] = create_manifest_stubs()
