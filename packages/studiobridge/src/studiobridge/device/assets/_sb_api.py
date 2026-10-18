"""_sb_api.py - FL Studio API allowlist and argument/return coercion.

Pure Python 3.9 syntax with zero external dependencies.
Generated deterministically by studiobridge.manifest.codegen. Do not edit manually.
"""

ALLOW = {
    "channels": {
        "channelCount": {
            "args": [
                {"name": "mode", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "int",
            "mutating": False,
        },
        "channelNumber": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getChannelColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getChannelName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "str",
            "mutating": False,
        },
        "getChannelPan": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getChannelPitch": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getChannelVolume": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getTargetFxTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "int",
            "mutating": False,
        },
        "incEventValue": {
            "args": [
                {"name": "eventId", "type": "int"},
                {"name": "value", "type": "int"},
                {"name": "step", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "isChannelMuted": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "isChannelSolo": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "muteChannel": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "selectChannel": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "value", "type": "int", "optional": True, "default": 1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "selectedChannel": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "setChannelColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "color", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setChannelName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "name", "type": "str"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getChannelName",
            "getter_args": [0],
            "compare": "exact",
            "settle": "immediate",
        },
        "setChannelPan": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "pan", "type": "float", "min": -1.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getChannelPan",
            "getter_args": [0],
            "compare": "approx",
            "tol": 0.01,
            "settle": "immediate",
        },
        "setChannelPitch": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "pitch", "type": "float"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setChannelVolume": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "volume", "type": "float", "min": 0.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getChannelVolume",
            "getter_args": [0],
            "compare": "approx",
            "tol": 0.01,
            "settle": "immediate",
        },
        "setTargetFxTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "track", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "none",
            "mutating": True,
        },
        "soloChannel": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "triggerNote": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "note", "type": "int", "optional": True, "default": 60},
                {"name": "velocity", "type": "int", "optional": True, "default": 100},
                {"name": "duration", "type": "int", "optional": True, "default": 1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getStepGrid": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
            ],
            "ret": "list",
            "mutating": False,
        },
        "setStepGrid": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "steps", "type": "list"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getStepGrid",
            "getter_args": [0],
            "compare": "exact",
            "settle": "immediate",
        },
    },
    "device": {
        "baseTrackSelect": {
            "args": [
                {"name": "offset", "type": "int"},
                {"name": "step", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "dispatch": {
            "args": [
                {"name": "messageId", "type": "int"},
                {"name": "value", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "forwardMIDICC": {
            "args": [
                {"name": "status", "type": "int"},
                {"name": "data1", "type": "int"},
                {"name": "data2", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getName": {
            "args": [],
            "ret": "str",
            "mutating": False,
        },
        "getPortNumber": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "isAssigned": {
            "args": [],
            "ret": "bool",
            "mutating": False,
        },
        "midiOutMsg": {
            "args": [
                {"name": "message", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "midiOutSysex": {
            "args": [
                {"name": "data", "type": "bytes"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "processMIDICC": {
            "args": [
                {"name": "event", "type": "int"},
            ],
            "ret": "int",
            "mutating": True,
        },
    },
    "general": {
        "clearChangedFlag": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
        "getChangedFlag": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getRecPPQ": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getVersion": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "processRECEvent": {
            "args": [
                {"name": "eventId", "type": "int"},
                {"name": "value", "type": "int"},
                {"name": "flags", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "int",
            "mutating": True,
        },
        "redo": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
        "restore": {
            "args": [],
            "ret": "none",
            "mutating": True,
            "protected": True,
        },
        "saveUndo": {
            "args": [
                {"name": "name", "type": "str"},
                {"name": "flags", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "undo": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
        "undoUp": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
    },
    "mixer": {
        "armTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "enableTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "enableTrackSlots": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getSongStepPos": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getTrackColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getTrackName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "str",
            "mutating": False,
        },
        "getTrackNumber": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getTrackPan": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getTrackSlotsEnabled": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "getTrackVolume": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "float",
            "mutating": False,
        },
        "isTrackArmed": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "isTrackEnabled": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "isTrackMuted": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "isTrackSolo": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "linkTrackToChannel": {
            "args": [
                {"name": "mode", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "muteTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "mixer.isTrackMuted",
            "getter_args": [0],
            "compare": "exact",
            "settle": "immediate",
        },
        "setTrackColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "color", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setTrackName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "name", "type": "str"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "mixer.getTrackName",
            "getter_args": [0],
            "compare": "exact",
            "settle": "immediate",
        },
        "setTrackNumber": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "number", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setTrackPan": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "pan", "type": "float", "min": -1.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "mixer.getTrackPan",
            "getter_args": [0],
            "compare": "approx",
            "tol": 0.01,
            "settle": "immediate",
        },
        "setTrackVolume": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "volume", "type": "float", "min": 0.0, "max": 1.0},
                {"name": "pickupMode", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "mixer.getTrackVolume",
            "getter_args": [0],
            "compare": "approx",
            "tol": 0.01,
            "settle": "idle1",
        },
        "soloTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "trackCount": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getTrackPeaks": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "mode", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getRouteTo": {
            "args": [
                {"name": "source", "type": "int", "min": 0, "max": 126},
                {"name": "dest", "type": "int", "min": 0, "max": 126},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "setRouteTo": {
            "args": [
                {"name": "source", "type": "int", "min": 0, "max": 126},
                {"name": "dest", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": 1},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "mixer.getRouteTo",
            "getter_args": [0, 1],
            "compare": "exact",
            "settle": "immediate",
        },
    },
    "patterns": {
        "ensureValidPattern": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getPatternColor": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getPatternLength": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getPatternName": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "str",
            "mutating": False,
        },
        "isPatternSelected": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "jumpToPattern": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "none",
            "mutating": True,
        },
        "patternCount": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "patternNumber": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "selectPattern": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
                {"name": "value", "type": "int", "optional": True, "default": 1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setPatternColor": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
                {"name": "color", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setPatternLength": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
                {"name": "length", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setPatternName": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
                {"name": "name", "type": "str"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "patterns.getPatternName",
            "getter_args": [0],
            "compare": "exact",
            "settle": "immediate",
        },
        "clearPattern": {
            "args": [
                {"name": "index", "type": "int", "min": 1, "max": 999},
            ],
            "ret": "none",
            "mutating": True,
        },
    },
    "plugins": {
        "getColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getColorName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "str",
            "mutating": False,
        },
        "getName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "str",
            "mutating": False,
        },
        "getParamCount": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getParamName": {
            "args": [
                {"name": "paramIndex", "type": "int"},
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "str",
            "mutating": False,
        },
        "getParamValue": {
            "args": [
                {"name": "paramIndex", "type": "int"},
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getPluginName": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "str",
            "mutating": False,
        },
        "getPresetCount": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "int",
            "mutating": False,
        },
        "getPresetName": {
            "args": [
                {"name": "presetIndex", "type": "int"},
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "str",
            "mutating": False,
        },
        "isValid": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "setParamValue": {
            "args": [
                {"name": "value", "type": "float", "min": 0.0, "max": 1.0},
                {"name": "paramIndex", "type": "int"},
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "showEditor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 999},
                {"name": "slot", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
    },
    "transport": {
        "continuousMove": {
            "args": [
                {"name": "value", "type": "int"},
                {"name": "step", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "fastForward": {
            "args": [
                {"name": "value", "type": "int", "optional": True, "default": 2},
                {"name": "step", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getLoopMode": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getPlaybackSpeed": {
            "args": [],
            "ret": "float",
            "mutating": False,
        },
        "getSongLength": {
            "args": [
                {"name": "mode", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "float",
            "mutating": False,
        },
        "getSongPos": {
            "args": [
                {"name": "mode", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "float",
            "mutating": False,
        },
        "globalTransport": {
            "args": [
                {"name": "command", "type": "int"},
                {"name": "value", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "int",
            "mutating": True,
        },
        "isPlaying": {
            "args": [],
            "ret": "bool",
            "mutating": False,
        },
        "isRecording": {
            "args": [],
            "ret": "bool",
            "mutating": False,
        },
        "markerJump": {
            "args": [
                {"name": "step", "type": "int"},
                {"name": "select", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "record": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
        "rewind": {
            "args": [
                {"name": "value", "type": "int", "optional": True, "default": 2},
                {"name": "step", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setLoopMode": {
            "args": [
                {"name": "mode", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "transport.getLoopMode",
            "getter_args": [],
            "compare": "exact",
            "settle": "immediate",
        },
        "setPlaybackSpeed": {
            "args": [
                {"name": "speed", "type": "float"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getTempo": {
            "args": [],
            "ret": "float",
            "mutating": False,
        },
        "setTempo": {
            "args": [
                {"name": "bpm", "type": "float"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "transport.getTempo",
            "getter_args": [],
            "compare": "approx",
            "tol": 0.1,
            "settle": "immediate",
        },
        "getMetronome": {
            "args": [],
            "ret": "bool",
            "mutating": False,
        },
        "setMetronome": {
            "args": [
                {"name": "enabled", "type": "bool", "optional": True, "default": True},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "transport.getMetronome",
            "getter_args": [],
            "compare": "exact",
            "settle": "immediate",
        },
        "getTimeSignature": {
            "args": [],
            "ret": "list",
            "mutating": False,
        },
        "setSongPos": {
            "args": [
                {"name": "pos", "type": "float", "min": 0.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "transport.getSongPos",
            "getter_args": [],
            "compare": "approx",
            "tol": 0.01,
            "settle": "idle1",
        },
        "start": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
        "stop": {
            "args": [],
            "ret": "none",
            "mutating": True,
        },
    },
    "ui": {
        "crDisplay": {
            "args": [
                {"name": "index", "type": "int"},
                {"name": "value", "type": "int"},
                {"name": "mode", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getFocused": {
            "args": [
                {"name": "window", "type": "int"},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "getStepEditMode": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getVersion": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "getVisible": {
            "args": [
                {"name": "window", "type": "int"},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "getVisibleForm": {
            "args": [
                {"name": "formId", "type": "int"},
            ],
            "ret": "bool",
            "mutating": False,
        },
        "hideWindow": {
            "args": [
                {"name": "window", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "jog": {
            "args": [
                {"name": "value", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "scrollWindow": {
            "args": [
                {"name": "window", "type": "int"},
                {"name": "delta", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setFocused": {
            "args": [
                {"name": "window", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setFocusedForm": {
            "args": [
                {"name": "formId", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "setStepEditMode": {
            "args": [
                {"name": "mode", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "showWindow": {
            "args": [
                {"name": "window", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "snapMode": {
            "args": [],
            "ret": "int",
            "mutating": False,
        },
        "snapWindow": {
            "args": [
                {"name": "window", "type": "int"},
                {"name": "mode", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
    },
}


def coerce_args(module_name, func_name, raw_args):
    """Validate and coerce raw arguments against the allowlist signature.

    Raises:
        KeyError: If module or function is not allowlisted (mapped to E_UNAVAILABLE).
        ValueError: If argument count or types/bounds violate constraints
            (mapped to E_ARGS).
    """
    mod_table = ALLOW.get(module_name)
    if mod_table is None:
        raise KeyError(f"Module '{module_name}' not allowlisted")

    spec = mod_table.get(func_name)
    if spec is None:
        raise KeyError(f"Function '{module_name}.{func_name}' not allowlisted")

    arg_specs = spec.get("args", [])
    raw_args = list(raw_args) if isinstance(raw_args, (list, tuple)) else []

    min_args = sum(1 for a in arg_specs if not a.get("optional", False))
    max_args = len(arg_specs)

    if len(raw_args) < min_args or len(raw_args) > max_args:
        raise ValueError(
            f"Expected between {min_args} and {max_args} arguments for "
            f"{module_name}.{func_name}, got {len(raw_args)}"
        )

    coerced = []
    for idx in range(len(raw_args)):
        arg_spec = arg_specs[idx]
        val = raw_args[idx]
        if val is None and arg_spec.get("optional", False):
            val = arg_spec.get("default")
        if val is None:
            arg_n = arg_spec["name"]
            raise ValueError(f"Argument '{arg_n}' cannot be None")
        arg_type = arg_spec.get("type", "int")
        try:
            if arg_type == "int":
                val = int(val)
                min_v = arg_spec.get("min")
                max_v = arg_spec.get("max")
                if min_v is not None and val < min_v:
                    an = arg_spec["name"]
                    raise ValueError(f"Argument {an} ({val}) < min {min_v}")
                if max_v is not None and val > max_v:
                    an = arg_spec["name"]
                    raise ValueError(f"Argument {an} ({val}) > max {max_v}")
            elif arg_type == "float":
                val = float(val)
                min_v = arg_spec.get("min")
                max_v = arg_spec.get("max")
                if min_v is not None and val < min_v:
                    an = arg_spec["name"]
                    raise ValueError(f"Argument {an} ({val}) < min {min_v}")
                if max_v is not None and val > max_v:
                    an = arg_spec["name"]
                    raise ValueError(f"Argument {an} ({val}) > max {max_v}")
            elif arg_type == "bool":
                val = bool(val)
            elif arg_type == "str":
                val = str(val)
            elif arg_type in ("list", "tuple"):
                val = list(val)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid value for argument '{arg_spec['name']}' of "
                f"{module_name}.{func_name}: {exc}"
            ) from exc
        coerced.append(val)

    return coerced


def normalize_ret(ret_type, val):
    """Normalize return value according to manifest expectations."""
    if ret_type == "none":
        return None
    elif ret_type == "bool":
        return bool(val)
    elif ret_type == "int":
        return int(val)
    elif ret_type == "float":
        return round(float(val), 6)
    elif ret_type == "str":
        return str(val)
    elif isinstance(val, (list, tuple)):
        return list(val)
    return val


def get_verify_getter(module_name, func_name, coerced_args):
    """Resolve paired getter function and argument list for verification."""
    spec = ALLOW.get(module_name, {}).get(func_name, {})
    getter_spec = spec.get("getter")
    if not getter_spec:
        return None, []
    getter_args_map = spec.get("getter_args", [])
    getter_args = [coerced_args[idx] for idx in getter_args_map if idx < len(coerced_args)]
    return getter_spec, getter_args


def is_protected(module_name, func_name):
    """Check if a function has the protected safety flag enabled."""
    mod = ALLOW.get(module_name, {})
    return bool(mod.get(func_name, {}).get("protected", False))
