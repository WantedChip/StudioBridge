"""_sb_api.py - FL Studio API allowlist and argument/return coercion.

Pure Python 3.9 syntax with zero external dependencies.
"""

ALLOW = {
    "transport": {
        "start": {"args": [], "ret": "none", "mutating": True},
        "stop": {"args": [], "ret": "none", "mutating": True},
        "isPlaying": {"args": [], "ret": "bool", "mutating": False},
        "record": {"args": [], "ret": "none", "mutating": True},
        "isRecording": {"args": [], "ret": "bool", "mutating": False},
        "setSongPos": {
            "args": [{"name": "pos", "type": "float", "min": 0.0, "max": 1.0}],
            "ret": "none",
            "mutating": True,
            "getter": "transport.getSongPos",
            "getter_args": [],
        },
        "getSongPos": {
            "args": [{"name": "mode", "type": "int", "optional": True, "default": 0}],
            "ret": "float",
            "mutating": False,
        },
        "getSongLength": {
            "args": [{"name": "mode", "type": "int", "optional": True, "default": 0}],
            "ret": "float",
            "mutating": False,
        },
        "setLoopMode": {"args": [], "ret": "none", "mutating": True},
        "getLoopMode": {"args": [], "ret": "int", "mutating": False},
        "globalTransport": {
            "args": [
                {"name": "command", "type": "int"},
                {"name": "value", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "int",
            "mutating": True,
        },
    },
    "mixer": {
        "trackCount": {"args": [], "ret": "int", "mutating": False},
        "getTrackVolume": {
            "args": [{"name": "index", "type": "int", "min": 0, "max": 126}],
            "ret": "float",
            "mutating": False,
        },
        "setTrackVolume": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "volume", "type": "float", "min": 0.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "mixer.getTrackVolume",
            "getter_args": [0],
        },
        "getTrackPan": {
            "args": [{"name": "index", "type": "int", "min": 0, "max": 126}],
            "ret": "float",
            "mutating": False,
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
        },
        "isTrackMuted": {
            "args": [{"name": "index", "type": "int", "min": 0, "max": 126}],
            "ret": "bool",
            "mutating": False,
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
        },
        "isTrackSolo": {
            "args": [{"name": "index", "type": "int", "min": 0, "max": 126}],
            "ret": "bool",
            "mutating": False,
        },
        "soloTrack": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getTrackName": {
            "args": [{"name": "index", "type": "int", "min": 0, "max": 126}],
            "ret": "str",
            "mutating": False,
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
        },
        "getTrackColor": {
            "args": [{"name": "index", "type": "int", "min": 0, "max": 126}],
            "ret": "int",
            "mutating": False,
        },
        "setTrackColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0, "max": 126},
                {"name": "color", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
    },
    "channels": {
        "channelCount": {
            "args": [{"name": "mode", "type": "int", "optional": True, "default": 0}],
            "ret": "int",
            "mutating": False,
        },
        "getChannelName": {
            "args": [{"name": "index", "type": "int", "min": 0}],
            "ret": "str",
            "mutating": False,
        },
        "setChannelName": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "name", "type": "str"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getChannelName",
            "getter_args": [0],
        },
        "getChannelVolume": {
            "args": [{"name": "index", "type": "int", "min": 0}],
            "ret": "float",
            "mutating": False,
        },
        "setChannelVolume": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "volume", "type": "float", "min": 0.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getChannelVolume",
            "getter_args": [0],
        },
        "getChannelPan": {
            "args": [{"name": "index", "type": "int", "min": 0}],
            "ret": "float",
            "mutating": False,
        },
        "setChannelPan": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "pan", "type": "float", "min": -1.0, "max": 1.0},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "channels.getChannelPan",
            "getter_args": [0],
        },
        "isChannelMuted": {
            "args": [{"name": "index", "type": "int", "min": 0}],
            "ret": "bool",
            "mutating": False,
        },
        "muteChannel": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "isChannelSolo": {
            "args": [{"name": "index", "type": "int", "min": 0}],
            "ret": "bool",
            "mutating": False,
        },
        "soloChannel": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "value", "type": "int", "optional": True, "default": -1},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getChannelColor": {
            "args": [{"name": "index", "type": "int", "min": 0}],
            "ret": "int",
            "mutating": False,
        },
        "setChannelColor": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "color", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "selectedChannel": {"args": [], "ret": "int", "mutating": False},
        "selectChannel": {
            "args": [
                {"name": "index", "type": "int", "min": 0},
                {"name": "value", "type": "int", "optional": True, "default": 1},
            ],
            "ret": "none",
            "mutating": True,
        },
    },
    "patterns": {
        "patternCount": {"args": [], "ret": "int", "mutating": False},
        "patternNumber": {"args": [], "ret": "int", "mutating": False},
        "getPatternName": {
            "args": [{"name": "index", "type": "int", "min": 1}],
            "ret": "str",
            "mutating": False,
        },
        "setPatternName": {
            "args": [
                {"name": "index", "type": "int", "min": 1},
                {"name": "name", "type": "str"},
            ],
            "ret": "none",
            "mutating": True,
            "getter": "patterns.getPatternName",
            "getter_args": [0],
        },
        "getPatternColor": {
            "args": [{"name": "index", "type": "int", "min": 1}],
            "ret": "int",
            "mutating": False,
        },
        "setPatternColor": {
            "args": [
                {"name": "index", "type": "int", "min": 1},
                {"name": "color", "type": "int"},
            ],
            "ret": "none",
            "mutating": True,
        },
        "getPatternLength": {
            "args": [{"name": "index", "type": "int", "min": 1}],
            "ret": "int",
            "mutating": False,
        },
        "jumpToPattern": {
            "args": [{"name": "index", "type": "int", "min": 1}],
            "ret": "none",
            "mutating": True,
        },
    },
    "general": {
        "getVersion": {"args": [], "ret": "int", "mutating": False},
        "getRecPPQ": {"args": [], "ret": "int", "mutating": False},
        "saveUndo": {
            "args": [
                {"name": "name", "type": "str"},
                {"name": "flags", "type": "int", "optional": True, "default": 0},
            ],
            "ret": "none",
            "mutating": True,
        },
        "undo": {"args": [], "ret": "none", "mutating": True},
        "redo": {"args": [], "ret": "none", "mutating": True},
        "undoUp": {"args": [], "ret": "none", "mutating": True},
    },
    "ui": {
        "getVersion": {"args": [], "ret": "int", "mutating": False},
        "getFocused": {
            "args": [{"name": "window", "type": "int"}],
            "ret": "bool",
            "mutating": False,
        },
        "setFocused": {
            "args": [{"name": "window", "type": "int"}],
            "ret": "none",
            "mutating": True,
        },
        "showWindow": {
            "args": [{"name": "window", "type": "int"}],
            "ret": "none",
            "mutating": True,
        },
        "hideWindow": {
            "args": [{"name": "window", "type": "int"}],
            "ret": "none",
            "mutating": True,
        },
        "getVisible": {
            "args": [{"name": "window", "type": "int"}],
            "ret": "bool",
            "mutating": False,
        },
    },
    "device": {
        "isAssigned": {"args": [], "ret": "bool", "mutating": False},
        "getPortNumber": {"args": [], "ret": "int", "mutating": False},
        "getName": {"args": [], "ret": "str", "mutating": False},
    },
}


def coerce_args(module_name, func_name, raw_args):
    """Validate and coerce raw arguments against the allowlist signature.

    Raises:
        KeyError: If module or function is not allowlisted (mapped to E_UNAVAILABLE).
        ValueError: If argument count or types/bounds violate constraints (mapped to E_ARGS).
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
    for idx, arg_spec in enumerate(arg_specs):
        val = raw_args[idx] if idx < len(raw_args) else arg_spec.get("default")
        arg_type = arg_spec.get("type", "int")
        try:
            if arg_type == "int":
                val = int(val)
                min_v = arg_spec.get("min")
                max_v = arg_spec.get("max")
                if min_v is not None and val < min_v:
                    raise ValueError(f"Argument {arg_spec['name']} ({val}) < min {min_v}")
                if max_v is not None and val > max_v:
                    raise ValueError(f"Argument {arg_spec['name']} ({val}) > max {max_v}")
            elif arg_type == "float":
                val = float(val)
                min_v = arg_spec.get("min")
                max_v = arg_spec.get("max")
                if min_v is not None and val < min_v:
                    raise ValueError(f"Argument {arg_spec['name']} ({val}) < min {min_v}")
                if max_v is not None and val > max_v:
                    raise ValueError(f"Argument {arg_spec['name']} ({val}) > max {max_v}")
            elif arg_type == "bool":
                val = bool(val)
            elif arg_type == "str":
                val = str(val)
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
