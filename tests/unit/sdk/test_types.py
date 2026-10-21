"""Unit tests for StudioBridge SDK untrusted string wrapper and data types."""

from __future__ import annotations

import json

from studiobridge.sdk.types import PluginInfo, PluginParam, ProjectInfo, UntrustedString


def test_untrusted_string_is_str() -> None:
    """Verify UntrustedString behaves as standard str with untrusted metadata."""
    s = UntrustedString("Harmor")
    assert isinstance(s, str)
    assert s == "Harmor"
    assert len(s) == 6
    assert s.startswith("Har")
    assert s.upper() == "HARMOR"
    assert s.untrusted is True

    # Dictionary representation contains untrusted flag
    d = s.to_dict()
    assert d["value"] == "Harmor"
    assert d["text"] == "Harmor"
    assert d["untrusted"] is True

    # JSON serializable as string
    serialized = json.dumps({"plugin": s})
    assert json.loads(serialized) == {"plugin": "Harmor"}


def test_sdk_types_untrusted_metadata() -> None:
    """Verify PluginInfo, PluginParam, ProjectInfo include untrusted strings and metadata."""
    param = PluginParam(
        track=1,
        slot=0,
        param_id=4,
        name=UntrustedString("Cutoff"),
        value=0.5,
        text=UntrustedString("1000 Hz"),
    )
    assert isinstance(param.name, UntrustedString)
    assert param.name.untrusted is True
    assert isinstance(param.text, UntrustedString)
    assert param.untrusted is True

    plugin = PluginInfo(
        track=1,
        slot=0,
        name=UntrustedString("Sytrus"),
        param_count=128,
        is_valid=True,
    )
    assert isinstance(plugin.name, UntrustedString)
    assert plugin.untrusted is True

    proj = ProjectInfo(
        title=UntrustedString("My Song"),
        author=UntrustedString("Producer"),
        comment=UntrustedString("Test project"),
    )
    assert isinstance(proj.title, UntrustedString)
    assert isinstance(proj.author, UntrustedString)
    assert isinstance(proj.comment, UntrustedString)
    assert proj.untrusted is True
