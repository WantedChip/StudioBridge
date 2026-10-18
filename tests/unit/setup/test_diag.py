"""Unit tests for redacted diagnostic bundle generation [DOC-02].

Verifies complete redaction of tokens, secrets, and credentials in the zip bundle.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from studiobridge.setup.diag import create_diagnostic_bundle


def test_diag_bundle_zero_secrets_grep(tmp_path: Path):
    """Verify acceptance criterion: sbridge diag produces bundle with zero secrets or tokens."""
    app_data = tmp_path / "AppData" / "Local" / "studiobridge"
    app_data.mkdir(parents=True, exist_ok=True)
    logs_dir = app_data / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    raw_secret_value = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    raw_token_value = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"

    # Seed secret and token files
    (app_data / "secret").write_text(raw_secret_value, encoding="utf-8")
    (app_data / "broker.token").write_text(raw_token_value, encoding="utf-8")

    # Seed config.toml
    config_content = (
        f'[broker]\nport = 50051\nbroker_token = "{raw_token_value}"\n'
        f'[wire]\nsecret = "{raw_secret_value}"\n'
    )
    (app_data / "config.toml").write_text(config_content, encoding="utf-8")

    # Seed log file
    log_file = logs_dir / "test.log"
    log_lines = [
        f"2026-10-18 INFO client auth token={raw_token_value}",
        f"2026-10-18 DEBUG wire frame secret: {raw_secret_value}",
        "2026-10-18 INFO normal operation without secrets",
    ]
    log_file.write_text("\n".join(log_lines), encoding="utf-8")

    # Generate diagnostic bundle
    out_zip = tmp_path / "test-diag.zip"
    result_path = create_diagnostic_bundle(out_path=out_zip, app_data_dir=app_data, skip_live=True)
    assert result_path.exists()
    assert result_path == out_zip

    # Verify contents of zip
    with zipfile.ZipFile(result_path, "r") as zf:
        namelist = zf.namelist()
        # Secret and token files must never be archived
        assert "secret" not in namelist
        assert "broker.token" not in namelist
        assert "doctor.json" in namelist
        assert "probe.json" in namelist
        assert "env.json" in namelist
        assert "config.toml" in namelist
        assert "logs/test.log" in namelist

        # Automated grep test: check every byte of every file in the zip
        for member_name in namelist:
            content_bytes = zf.read(member_name)
            content_text = content_bytes.decode("utf-8", errors="replace")

            # Must contain zero occurrences of raw secret or token
            assert raw_secret_value not in content_text, f"Secret leaked in {member_name}"
            assert raw_token_value not in content_text, f"Token leaked in {member_name}"

            # If json file, verify it parses validly
            if member_name.endswith(".json"):
                parsed = json.loads(content_text)
                assert isinstance(parsed, dict)
