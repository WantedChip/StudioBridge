"""Unit tests for StudioBridge safety policy parsing and boundary enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from studiobridge.core.errors import PolicyDeniedError
from studiobridge.sdk.policy import Policy


def test_policy_default_permissive() -> None:
    """Verify default policy has no restrictions."""
    policy = Policy()
    assert policy.deny_ops == set()
    assert policy.max_volume_db is None
    assert policy.max_volume is None
    assert policy.max_volume_delta_db is None
    assert policy.max_tempo is None
    assert policy.min_tempo is None
    assert policy.protect_tempo is False
    assert policy.allow_protected is False

    # Permissive check should not raise
    policy.check("mixer.setTrackVolume", {"index": 1, "volume": 1.0})
    policy.check("transport.setTempo", {"bpm": 128.0})


def test_policy_from_toml_deny_ops(tmp_path: Path) -> None:
    """Verify policy parsing deny_ops and enforcement."""
    toml_content = """
    [policy]
    deny_ops = ["project.save", "mixer.routeTrack"]
    """
    policy_file = tmp_path / ".sbridge-policy.toml"
    policy_file.write_text(toml_content, encoding="utf-8")

    policy = Policy.load(policy_file)
    assert "project.save" in policy.deny_ops
    assert "mixer.routeTrack" in policy.deny_ops

    # Denied op should raise PolicyDeniedError (E_POLICY)
    with pytest.raises(PolicyDeniedError) as exc_info:
        policy.check("project.save", {})
    assert exc_info.value.code == "E_POLICY"
    assert "denied by active safety policy" in str(exc_info.value)

    # Allowed op should pass
    policy.check("mixer.setTrackVolume", {"index": 1, "volume": 0.8})


def test_policy_volume_bounds() -> None:
    """Verify policy max_volume and max_volume_db enforcement."""
    policy = Policy.from_dict(
        {
            "policy": {
                "max_volume": 0.8,
                "max_volume_db": 0.0,
            }
        }
    )

    # Within bounds passes
    policy.check("mixer.setTrackVolume", {"index": 1, "volume": 0.8})
    policy.check("mixer.setTrackVolume", {"index": 1, "volume": -3.0})

    # Exceeding normalized volume raises PolicyDeniedError
    with pytest.raises(PolicyDeniedError) as exc_info:
        policy.check("mixer.setTrackVolume", {"index": 1, "volume": 0.85})
    assert exc_info.value.code == "E_POLICY"
    assert "exceeds policy limit" in str(exc_info.value)

    # Exceeding dB volume raises PolicyDeniedError
    with pytest.raises(PolicyDeniedError) as exc_info_db:
        policy.check("mixer.setTrackVolume", {"index": 1, "volume": 3.0})
    assert exc_info_db.value.code == "E_POLICY"


def test_policy_volume_delta_bounds() -> None:
    """Verify max_volume_delta_db prevents sudden volume jumps."""
    policy = Policy.from_dict(
        {
            "policy": {
                "max_volume_delta_db": 6.0,
            }
        }
    )

    # Delta of 3 dB is permitted (e.g. 0.0 dB -> -3.0 dB)
    policy.check(
        "mixer.setTrackVolume",
        {"index": 1, "volume": 0.7},
        context={"current_volume": 0.8},
    )

    # Jump of >6 dB (e.g. 0.1 normalized ~ -20 dB to 0.8 normalized ~ 0 dB)
    with pytest.raises(PolicyDeniedError) as exc_info:
        policy.check(
            "mixer.setTrackVolume",
            {"index": 1, "volume": 1.0},
            context={"current_volume": 0.1},
        )
    assert exc_info.value.code == "E_POLICY"
    assert "delta" in str(exc_info.value).lower()


def test_policy_tempo_bounds() -> None:
    """Verify max_tempo and min_tempo bounds."""
    policy = Policy.from_dict(
        {
            "policy": {
                "min_tempo": 60.0,
                "max_tempo": 200.0,
                "protect_tempo": True,
            }
        }
    )
    assert policy.protect_tempo is True

    # 120 BPM passes
    policy.check("transport.setTempo", {"bpm": 120.0})

    # Too fast raises
    with pytest.raises(PolicyDeniedError) as exc_max:
        policy.check("transport.setTempo", {"bpm": 220.0})
    assert exc_max.value.code == "E_POLICY"

    # Too slow raises
    with pytest.raises(PolicyDeniedError) as exc_min:
        policy.check("transport.setTempo", {"bpm": 45.0})
    assert exc_min.value.code == "E_POLICY"


def test_policy_load_hierarchy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Policy.load resolution order."""
    sub_dir = tmp_path / "sub" / "project"
    sub_dir.mkdir(parents=True)
    policy_file = tmp_path / ".sbridge-policy.toml"
    policy_file.write_text('deny_ops = ["custom.action"]', encoding="utf-8")

    monkeypatch.chdir(sub_dir)
    loaded = Policy.load()
    assert "custom.action" in loaded.deny_ops
