"""Automated security gate verification and pre-release security review script.

Executes the comprehensive 7-point Security Review Checklist:
1. SEC-01: HMAC signatures on all mutating wire operations & monotonic MID replay defense.
2. SEC-02: Broker loopback-only binding (127.0.0.1) & 2-second connection timeout.
3. SEC-03: Zero credentials, tokens, or private paths in logs and diagnostics bundles.
4. SEC-04: Path traversal defenses, null byte checks, and allowed root containment.
5. SEC-05: Prompt injection markers and untrusted metadata tags for FL Studio content.
6. SEC-06: Elimination of raw exec/eval execution from release builds.
7. SEC-07: Dependency lockfile pinning and Software Bill of Materials (SBOM) generation.

CLI Options:
  --check        Exit with status code 0 if all checks pass, 1 otherwise.
  --json         Emit structured JSON report to standard output.
  --quiet        Suppress verbose output; print only summary or failures.
  --sbom-out PATH Write generated CycloneDX SBOM JSON to the specified path.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Python 3.11+ built-in tomllib with fallback
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class CheckResult:
    """Result of a single security checklist verification."""

    id: str
    title: str
    passed: bool
    details: str
    findings: list[str] = field(default_factory=list)


@dataclass
class SecurityAuditReport:
    """Aggregated security review report."""

    timestamp: str
    overall_passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    sbom: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert report to serializable dictionary."""
        return {
            "timestamp": self.timestamp,
            "overall_passed": self.overall_passed,
            "summary": self.summary,
            "checks": [asdict(c) for c in self.checks],
            "sbom_included": self.sbom is not None,
        }


# -----------------------------------------------------------------------------
# Check 1: HMAC Signatures & Monotonic Replay Defense (SEC-01)
# -----------------------------------------------------------------------------


def check_hmac_and_replay_defense(repo_root: Path) -> CheckResult:
    """Verify HMAC-SHA256 request authentication and monotonic MID replay rejection."""
    findings: list[str] = []

    try:
        from studiobridge.wire.auth import UNAUTHENTICATED_OPS, verify_request
        from studiobridge.wire.envelope import RequestEnvelope
        from studiobridge.wire.session import Session

        # 1. Verify unauthenticated ops are strictly minimal
        expected_unauth = frozenset({"hello", "ping"})
        if expected_unauth != UNAUTHENTICATED_OPS:
            findings.append(
                f"UNAUTHENTICATED_OPS unexpected: {UNAUTHENTICATED_OPS} != {expected_unauth}"
            )

        # 2. Verify HMAC signature check rejects invalid signature
        secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        test_env = RequestEnvelope(
            op="channel.set_volume",
            idem="id-1",
            args={"index": 0, "val": 0.8},
        )
        test_env.auth = "invalid_signature_hex"
        if verify_request(secret, test_env):
            findings.append("verify_request accepted invalid HMAC signature on mutating op")

        # 3. Verify monotonic MID replay rejection
        session = Session.allocate()
        session.last_mutating_mid = 10
        mutating_env = RequestEnvelope(
            op="call",
            idem="id-2",
            args={"fn": "mixer.set_volume"},
        )
        mutating_env.opts.fp = session.fp

        try:
            session.validate_incoming_request(mutating_env, mid=10)
            findings.append("Session did not reject replayed MID 10 <= 10")
        except Exception as exc:
            if getattr(exc, "code", "") != "E_AUTH":
                findings.append(f"Replayed MID raised unexpected error code: {exc}")

        try:
            session.validate_incoming_request(mutating_env, mid=9)
            findings.append("Session did not reject decremented MID 9 <= 10")
        except Exception as exc:
            if getattr(exc, "code", "") != "E_AUTH":
                findings.append(f"Decremented MID raised unexpected error code: {exc}")

    except Exception as exc:
        findings.append(f"Failed executing HMAC/replay verification check: {exc}")

    passed = len(findings) == 0
    details = (
        "HMAC-SHA256 signature verification and monotonic MID replay rejection active"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-01",
        title="HMAC Signatures & Replay Defense",
        passed=passed,
        details=details,
        findings=findings,
    )


# -----------------------------------------------------------------------------
# Check 2: Broker Loopback-Only Binding & Connection Timeout (SEC-02)
# -----------------------------------------------------------------------------


def check_broker_loopback_and_auth_timeout(repo_root: Path) -> CheckResult:
    """Verify broker binds strictly to loopback and unauth connections time out <= 2.0s."""
    findings: list[str] = []

    try:
        from studiobridge.broker.server import DEFAULT_AUTH_TIMEOUT, BrokerServer
        from studiobridge.core.errors import SecurityError
        from studiobridge.http.server import LOOPBACK_HOSTS

        # 1. Verify default timeout is <= 2.0s
        if DEFAULT_AUTH_TIMEOUT > 2.0:
            findings.append(
                f"DEFAULT_AUTH_TIMEOUT is {DEFAULT_AUTH_TIMEOUT}s, exceeds 2.0s threshold"
            )

        # 2. Verify non-loopback bind is strictly rejected
        for forbidden_host in ("0.0.0.0", "192.168.1.50", "example.com"):
            try:
                BrokerServer(host=forbidden_host, port=0)
                findings.append(f"BrokerServer allowed non-loopback host: '{forbidden_host}'")
            except SecurityError:
                pass  # Correctly rejected
            except Exception as exc:
                findings.append(
                    f"BrokerServer raised non-SecurityError on '{forbidden_host}': {exc}"
                )

        # 3. Verify HTTP server restricts to loopback hosts
        if not LOOPBACK_HOSTS.issubset({"127.0.0.1", "localhost", "::1"}):
            findings.append(f"HTTP LOOPBACK_HOSTS has non-loopback entries: {LOOPBACK_HOSTS}")

    except Exception as exc:
        findings.append(f"Failed verifying broker loopback binding: {exc}")

    passed = len(findings) == 0
    details = (
        "Broker strictly binds to 127.0.0.1 and enforces 2.0s auth timeout"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-02",
        title="Broker Loopback Binding & Auth Timeout",
        passed=passed,
        details=details,
        findings=findings,
    )


# -----------------------------------------------------------------------------
# Check 3: Secret & Token Redaction (SEC-03)
# -----------------------------------------------------------------------------


def check_secret_redaction(repo_root: Path) -> CheckResult:
    """Verify automated secret masking in strings, logs, errors, and diagnostic bundles."""
    findings: list[str] = []

    try:
        from studiobridge.core.errors import SecurityError
        from studiobridge.core.logging import (
            redact_string,
        )

        # 1. Test string redactor on 64-char hex secret
        sample_hex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        masked_hex = redact_string(f"token={sample_hex}")
        if sample_hex in masked_hex:
            findings.append("redact_string leaked 64-character hex secret")

        # 2. Test bearer token redaction
        sample_bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        masked_bearer = redact_string(f"Authorization: {sample_bearer}")
        if sample_bearer in masked_bearer or "Bearer [REDACTED]" not in masked_bearer:
            findings.append("redact_string leaked Bearer token")

        # 3. Test private path redaction
        sample_win_path = r"C:\Users\SecretDev\Projects\music.flp"
        masked_path = redact_string(sample_win_path)
        if "SecretDev" in masked_path:
            findings.append("redact_string leaked Windows user profile directory")

        # 4. Test error to_dict sanitization
        err = SecurityError(
            f"Failed with token={sample_hex}",
            code="E_SECURITY",
            remedy=f"Check password=plain_secret in {sample_win_path}",
            details={"secret": sample_hex},
        )
        d = err.to_dict()
        if sample_hex in str(d) or "plain_secret" in str(d) or "SecretDev" in str(d):
            findings.append("StudioBridgeError.to_dict() leaked sensitive credentials")

        # 5. Static codebase scan for hardcoded private keys or passwords
        code_dir = repo_root / "packages" / "studiobridge" / "src"
        private_key_pattern = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")

        if code_dir.exists():
            for py_path in code_dir.rglob("*.py"):
                text = py_path.read_text(encoding="utf-8", errors="ignore")
                if private_key_pattern.search(text):
                    rel = py_path.relative_to(repo_root)
                    findings.append(f"Potential hardcoded private key in source: {rel}")

    except Exception as exc:
        findings.append(f"Failed verifying secret redaction: {exc}")

    passed = len(findings) == 0
    details = (
        "Tokens, bearer auth, passwords, and private paths automatically redacted"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-03",
        title="Secret & Token Redaction",
        passed=passed,
        details=details,
        findings=findings,
    )


# -----------------------------------------------------------------------------
# Check 4: Path Traversal & Containment Allowlists (SEC-04)
# -----------------------------------------------------------------------------


def check_path_containment_allowlists(repo_root: Path) -> CheckResult:
    """Verify that path normalization and allowed root directory checks reject traversal."""
    findings: list[str] = []

    try:
        from studiobridge.core.errors import SecurityError
        from studiobridge.core.paths import validate_safe_path

        # 1. Directory traversal sequence rejection
        traversals = ("../../etc/passwd", "..\\..\\Windows\\System32\\cmd.exe", "foo/../../bar")
        for traversal in traversals:
            try:
                validate_safe_path(traversal)
                findings.append(f"validate_safe_path failed to reject traversal: '{traversal}'")
            except SecurityError:
                pass
            except Exception as exc:
                findings.append(
                    f"validate_safe_path raised unexpected error on '{traversal}': {exc}"
                )

        # 2. Embedded null byte rejection
        try:
            validate_safe_path("path\0evil.flp")
            findings.append("validate_safe_path failed to reject embedded null byte")
        except SecurityError:
            pass
        except Exception as exc:
            findings.append(f"validate_safe_path raised unexpected error on null byte: {exc}")

        # 3. Unauthorized UNC path rejection
        for unc in (r"\\evil-server\share\file.flp", "//evil-server/share/file.flp"):
            try:
                validate_safe_path(unc, allow_unc=False)
                findings.append(f"validate_safe_path failed to reject UNC path: '{unc}'")
            except SecurityError:
                pass
            except Exception as exc:
                findings.append(f"validate_safe_path raised unexpected error on UNC path: {exc}")

        # 4. URL-encoded traversal rejection
        try:
            validate_safe_path("%2e%2e/etc/passwd")
            findings.append("validate_safe_path failed to reject URL-encoded traversal")
        except SecurityError:
            pass
        except Exception as exc:
            findings.append(
                f"validate_safe_path raised unexpected error on URL-encoded path: {exc}"
            )

    except Exception as exc:
        findings.append(f"Failed verifying path containment allowlists: {exc}")

    passed = len(findings) == 0
    details = (
        "Path traversal (..), null bytes, UNC paths, and directory escapes strictly blocked"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-04",
        title="Path Traversal & Containment Allowlists",
        passed=passed,
        details=details,
        findings=findings,
    )


# -----------------------------------------------------------------------------
# Check 5: Prompt Injection Defense & Untrusted Markers (SEC-05)
# -----------------------------------------------------------------------------


def check_prompt_injection_defense(repo_root: Path) -> CheckResult:
    """Verify prompt-injection defense metadata and system instructions word budget."""
    findings: list[str] = []

    try:
        from studiobridge.mcp.instructions import (
            SERVER_INSTRUCTIONS,
            UNTRUSTED_METADATA,
            is_untrusted,
            mark_untrusted,
        )

        # 1. Word budget validation (<= 120 words)
        words = len(SERVER_INSTRUCTIONS.split())
        if words > 120:
            findings.append(f"SERVER_INSTRUCTIONS exceeds 120 words budget: {words} words")

        # 2. Critical instruction content check
        lower_inst = SERVER_INSTRUCTIONS.lower()
        if "untrusted" not in lower_inst or "never interpret" not in lower_inst:
            findings.append("SERVER_INSTRUCTIONS missing explicit untrusted guidance warning")

        # 3. Untrusted metadata tag check
        if UNTRUSTED_METADATA.get("untrusted") is not True:
            findings.append("UNTRUSTED_METADATA does not have untrusted=True")

        # 4. Untrusted marking functionality
        tagged = mark_untrusted({"name": "User Track"})
        if not is_untrusted(tagged):
            findings.append("mark_untrusted did not tag dictionary with untrusted marker")

    except Exception as exc:
        findings.append(f"Failed verifying prompt injection defense: {exc}")

    passed = len(findings) == 0
    details = (
        "Server instructions (<= 120 words) and untrusted metadata markers active"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-05",
        title="Prompt Injection Defense & Markers",
        passed=passed,
        details=details,
        findings=findings,
    )


# -----------------------------------------------------------------------------
# Check 6: Raw Exec/Eval Elimination (SEC-06)
# -----------------------------------------------------------------------------


def check_raw_exec_elimination(repo_root: Path) -> CheckResult:
    """Verify that raw exec and eval calls are eliminated from release packages."""
    findings: list[str] = []
    code_dir = repo_root / "packages" / "studiobridge" / "src"

    # Whitelisted sandbox runner (strictly local mock test harness emulator)
    emulator_rel = (
        Path("packages")
        / "studiobridge"
        / "src"
        / "studiobridge"
        / "device"
        / "emulator"
        / "runner.py"
    )
    whitelisted_emulator = (repo_root / emulator_rel).resolve()

    if code_dir.exists():
        for py_path in code_dir.rglob("*.py"):
            resolved = py_path.resolve()
            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8"))
            except Exception as exc:
                findings.append(f"Could not parse AST for {py_path}: {exc}")
                continue

            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("exec", "eval")
                ):
                    if node.func.id == "exec" and resolved == whitelisted_emulator:
                        continue  # Authorized mock emulator runner
                    rel = py_path.relative_to(repo_root)
                    findings.append(
                        f"Insecure raw {node.func.id}() in release code at {rel}:{node.lineno}"
                    )

    passed = len(findings) == 0
    details = (
        "Zero raw eval() calls; exec() eliminated from production codebase (emulator harness only)"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-06",
        title="Raw Exec/Eval Elimination",
        passed=passed,
        details=details,
        findings=findings,
    )


# -----------------------------------------------------------------------------
# Check 7: Dependency Lockfile Pinning & SBOM Generation (SEC-07)
# -----------------------------------------------------------------------------


def generate_sbom(repo_root: Path) -> dict[str, Any]:
    """Parse uv.lock and produce standard CycloneDX 1.5 JSON SBOM payload."""
    lock_file = repo_root / "uv.lock"
    if not lock_file.exists():
        raise FileNotFoundError("uv.lock file not found")

    if tomllib is None:
        raise ImportError("tomllib or tomli required to parse uv.lock")

    lock_data = tomllib.loads(lock_file.read_text(encoding="utf-8"))
    packages = lock_data.get("package", [])

    components: list[dict[str, Any]] = []
    for pkg in packages:
        name = pkg.get("name", "")
        version = pkg.get("version", "")
        sdist = pkg.get("sdist", {})
        wheels = pkg.get("wheels", [])

        hashes: list[dict[str, str]] = []
        if isinstance(sdist, dict) and "hash" in sdist:
            h_str = sdist["hash"]
            if ":" in h_str:
                alg, val = h_str.split(":", 1)
                hashes.append({"alg": alg.upper(), "content": val})

        for whl in wheels:
            if isinstance(whl, dict) and "hash" in whl:
                h_str = whl["hash"]
                if ":" in h_str:
                    alg, val = h_str.split(":", 1)
                    hashes.append({"alg": alg.upper(), "content": val})

        component: dict[str, Any] = {
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
        }
        if hashes:
            component["hashes"] = hashes
        components.append(component)

    tool_info = {
        "vendor": "WantedChip",
        "name": "StudioBridge Security Auditor",
        "version": "0.1.0",
    }
    app_info = {
        "type": "application",
        "name": "studiobridge",
        "version": "0.1.0",
        "description": "StudioBridge control bridge and MCP server for FL Studio",
    }
    sbom: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": (f"urn:uuid:{hashlib.sha256(lock_file.read_bytes()).hexdigest()[:36]}"),
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [tool_info],
            "component": app_info,
        },
        "components": sorted(components, key=lambda c: c["name"]),
    }
    return sbom


def check_dependency_pinning_and_sbom(
    repo_root: Path,
) -> tuple[CheckResult, dict[str, Any] | None]:
    """Verify that dependencies are pinned in uv.lock and generate CycloneDX SBOM."""
    findings: list[str] = []
    sbom: dict[str, Any] | None = None

    lock_file = repo_root / "uv.lock"
    if not lock_file.exists():
        findings.append("Missing uv.lock dependency lockfile")
    else:
        try:
            sbom = generate_sbom(repo_root)
            total_components = len(sbom.get("components", []))
            if total_components == 0:
                findings.append("Parsed uv.lock but found zero dependency components")
        except Exception as exc:
            findings.append(f"Failed parsing uv.lock or generating SBOM: {exc}")

    passed = len(findings) == 0
    total = len(sbom.get("components", [])) if sbom else 0
    details = (
        f"uv.lock verified with {total} pinned dependencies; CycloneDX 1.5 SBOM generated"
        if passed
        else f"Failed: {', '.join(findings)}"
    )
    return CheckResult(
        id="SEC-07",
        title="Dependency Pinning & SBOM",
        passed=passed,
        details=details,
        findings=findings,
    ), sbom


# -----------------------------------------------------------------------------
# Main Audit Orchestration
# -----------------------------------------------------------------------------


def run_security_audit(
    repo_root: Path | None = None,
    *,
    generate_sbom_payload: bool = True,
) -> SecurityAuditReport:
    """Execute the full 7-point pre-release security review checklist."""
    root = (repo_root or Path.cwd()).resolve()
    # Walk up if running from inside tools/ or packages/
    while not (root / "pyproject.toml").exists() and root.parent != root:
        root = root.parent

    # Add studiobridge package to sys.path if not installed
    sb_pkg = root / "packages" / "studiobridge" / "src"
    if sb_pkg.exists() and str(sb_pkg) not in sys.path:
        sys.path.insert(0, str(sb_pkg))

    checks: list[CheckResult] = []

    # 1. HMAC & Replay Defense
    checks.append(check_hmac_and_replay_defense(root))

    # 2. Broker Loopback & Timeout
    checks.append(check_broker_loopback_and_auth_timeout(root))

    # 3. Secret & Token Redaction
    checks.append(check_secret_redaction(root))

    # 4. Path Traversal & Containment
    checks.append(check_path_containment_allowlists(root))

    # 5. Prompt Injection Defense
    checks.append(check_prompt_injection_defense(root))

    # 6. Raw Exec/Eval Elimination
    checks.append(check_raw_exec_elimination(root))

    # 7. Dependency Pinning & SBOM
    check7, sbom = check_dependency_pinning_and_sbom(root)
    checks.append(check7)

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = sum(1 for c in checks if not c.passed)
    overall_passed = failed_count == 0

    return SecurityAuditReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        overall_passed=overall_passed,
        checks=checks,
        summary={"total": len(checks), "passed": passed_count, "failed": failed_count},
        sbom=sbom if generate_sbom_payload else None,
    )


def main(argv: list[str] | None = None) -> int:
    """Command-line entrypoint for the security audit script."""
    parser = argparse.ArgumentParser(
        description="StudioBridge Automated Pre-Release Security Review and Audit Gate"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run security checks and exit with code 0 on pass, 1 on fail.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON audit report to standard output.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose progress messages.",
    )
    parser.add_argument(
        "--sbom-out",
        type=Path,
        metavar="PATH",
        help="Save generated CycloneDX SBOM JSON to specified file path.",
    )

    args = parser.parse_args(argv)
    report = run_security_audit()

    # Save SBOM if requested
    if args.sbom_out and report.sbom:
        args.sbom_out.parent.mkdir(parents=True, exist_ok=True)
        args.sbom_out.write_text(json.dumps(report.sbom, indent=2), encoding="utf-8")

    # Output formatting
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif not args.quiet:
        status_banner = "ALL CHECKS PASSED" if report.overall_passed else "VIOLATIONS DETECTED"
        print("=" * 72)
        print(" StudioBridge Automated Security Review Audit")
        print("=" * 72)
        print(f" Timestamp: {report.timestamp}")
        print(f" Status:    {status_banner}")
        print("-" * 72)
        for c in report.checks:
            status_tag = "[PASS]" if c.passed else "[FAIL]"
            print(f" {status_tag} {c.id} - {c.title}")
            print(f"        {c.details}")
            if c.findings:
                for f in c.findings:
                    print(f"        ! Finding: {f}")
        print("-" * 72)
        summary = report.summary
        passed_str = f"{summary['passed']}/{summary['total']} checks passed"
        print(f" Summary: {passed_str} ({summary['failed']} failed)")
        print("=" * 72)
    elif not report.overall_passed:
        # Quiet mode: only print errors if any check failed
        for c in report.checks:
            if not c.passed:
                print(f"[FAIL] {c.id} - {c.title}: {c.details}", file=sys.stderr)

    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
