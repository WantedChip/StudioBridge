"""Redacted diagnostic zip bundle generator [DOC-02].

Creates a shareable diagnostics bundle (sbridge diag) containing environment facts,
doctor check results, capability probe data, sanitized configuration, and recent logs.
Strictly redacts all secrets, tokens, passwords, and credentials so issue reports
can be safely shared publicly.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studiobridge._version import __version__
from studiobridge.core.logging import get_logger, redact_sensitive_data, redact_string
from studiobridge.core.paths import get_app_data_dir
from studiobridge.setup.doctor import Doctor, DoctorReport
from studiobridge.setup.probe import ProbeReport, run_probe

logger = get_logger("setup.diag")


def generate_env_info() -> dict[str, Any]:
    """Gather non-sensitive environment metadata."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "studiobridge_version": __version__,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "architecture": platform.architecture()[0],
        },
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "prefix": sys.prefix,
        },
        "environment_variables": {
            k: redact_string(v)
            for k, v in os.environ.items()
            if any(term in k.lower() for term in ("sbridge", "fl", "path", "python", "onedrive"))
        },
    }


def create_diagnostic_bundle(
    out_path: Path | None = None,
    *,
    doctor_report: DoctorReport | None = None,
    probe_report: ProbeReport | None = None,
    app_data_dir: Path | None = None,
    skip_live: bool = True,
) -> Path:
    """Generate a redacted zip bundle for troubleshooting and bug reporting.

    Guarantees [DOC-02]:
    1. Zero unredacted secrets or tokens in any included file.
    2. %LOCALAPPDATA%\\studiobridge\\secret and broker.token are strictly excluded.
    3. Logs and configuration files are passed through string and object redaction filters.
    """
    app_data = app_data_dir or get_app_data_dir()
    logs_dir = app_data / "logs"

    # Default output path
    if out_path is None:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = app_data / f"studiobridge-diag-{timestamp_str}.zip"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Run or accept doctor and probe reports
    if doctor_report is None:
        doc = Doctor(app_data_dir=app_data, skip_live=skip_live)
        doctor_report = doc.run()

    if probe_report is None:
        probe_report = run_probe(app_data_dir=app_data)

    env_info = generate_env_info()

    # 2. Build sanitized zip file
    with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # A. doctor.json
        doc_json = json.dumps(redact_sensitive_data(doctor_report.to_dict()), indent=2)
        zf.writestr("doctor.json", doc_json)

        # B. probe.json
        probe_json = json.dumps(redact_sensitive_data(probe_report.to_dict()), indent=2)
        zf.writestr("probe.json", probe_json)

        # C. env.json
        env_json = json.dumps(redact_sensitive_data(env_info), indent=2)
        zf.writestr("env.json", env_json)

        # D. config.toml (sanitized)
        config_path = app_data / "config.toml"
        if config_path.exists():
            try:
                raw_cfg = config_path.read_text(encoding="utf-8")
                sanitized_cfg = redact_string(raw_cfg)
                zf.writestr("config.toml", sanitized_cfg)
            except Exception as exc:
                logger.warning("diag_config_error", f"Failed reading config.toml: {exc}")

        # E. setup-report.json (sanitized)
        setup_report_path = app_data / "setup-report.json"
        if setup_report_path.exists():
            try:
                raw_report = json.loads(setup_report_path.read_text(encoding="utf-8"))
                sanitized_report = redact_sensitive_data(raw_report)
                zf.writestr("setup-report.json", json.dumps(sanitized_report, indent=2))
            except Exception as exc:
                logger.warning("diag_setup_report_error", f"Failed reading setup-report: {exc}")

        # F. logs/*.log and logs/*.jsonl (sanitized line by line)
        if logs_dir.exists():
            try:
                for log_file in sorted(logs_dir.glob("*.log")) + sorted(logs_dir.glob("*.jsonl")):
                    if log_file.is_file():
                        try:
                            lines: list[str] = []
                            for line in log_file.read_text(encoding="utf-8").splitlines():
                                lines.append(redact_string(line))
                            sanitized_log = "\n".join(lines)
                            zf.writestr(f"logs/{log_file.name}", sanitized_log)
                        except Exception as exc:
                            logger.warning(
                                "diag_log_read_error",
                                f"Failed reading log {log_file.name}: {exc}",
                            )
            except Exception as exc:
                logger.warning("diag_logs_error", f"Failed reading logs directory: {exc}")

    logger.info("diag_bundle_created", f"Created diagnostics bundle at {out_path}")
    return out_path
