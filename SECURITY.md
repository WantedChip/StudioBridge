# Security Policy

StudioBridge is designed with safety, local containment, and defense-in-depth as fundamental architecture requirements.

---

## Supported Versions

Only the latest major/minor release receives active security patches:

| Version | Supported | Notes |
| :--- | :---: | :--- |
| `1.0.x` | :white_check_mark: | Current stable release |
| `< 1.0` | :x: | Alpha and development builds |

---

## Reporting a Vulnerability

If you discover a security vulnerability in StudioBridge, please do **NOT** open a public issue or discuss it in public chat channels.

Please report the vulnerability responsibly via private email:

- **Security Contact:** `ty121rt@gmail.com`
- **Subject:** `[VULNERABILITY] StudioBridge - <Brief Description>`

### What to Include in Your Report

To help us triage and resolve the issue quickly, please include:
1. Description of the vulnerability and its potential impact.
2. Step-by-step reproduction instructions or proof-of-concept (PoC) script.
3. Affected components (e.g. HTTP server, MCP server, FLP engine, broker).
4. System environment details (OS, Python version, architecture).

### Vulnerability Handling Process

- **Acknowledgment:** We will acknowledge receipt of your vulnerability report within 48 hours.
- **Triage & Assessment:** We will provide an initial assessment and reproduction timeline within 7 days.
- **Coordination & Fix:** A security patch will be developed, tested against our automated test suites, and released with coordinated disclosure credit.

---

## Security Model & Guarantees

StudioBridge implements the following security controls:

1. **Loopback Isolation:**
   - Both the Broker daemon and the optional HTTP REST server bind strictly to `127.0.0.1`. Non-loopback bindings (`0.0.0.0` or external network adapters) are explicitly rejected.
2. **Bearer Token Authentication:**
   - All client connections must authenticate with the local Bearer token generated at `%LOCALAPPDATA%\studiobridge\broker.token`.
   - Token comparisons utilize constant-time `hmac.compare_digest` to prevent timing side-channel attacks.
3. **Path Traversal Containment:**
   - All file-accepting MCP tools and CLI arguments are validated against strict directory containment allowlists. Directory escapes (`..`), embedded null bytes, URL-encoded sequences, and unauthorized UNC paths are rejected with `SecurityError`.
4. **Safety Interlock Levels:**
   - By default, sessions operate in `READ_ONLY` mode. Any mutating action requires an explicit confirmation challenge token or explicit session mode elevation.
5. **Prompt Injection Mitigation:**
   - All MCP tool descriptions are bounded by a strict word budget (`<= 120` words) and enforce explicit untrusted metadata tagging for file names, track names, and project comments.
6. **Zero Raw Exec:**
   - The production codebase contains zero calls to `eval()` or dynamic `exec()`.
7. **Supply Chain Security:**
   - All third-party dependencies are pinned in `uv.lock`. Every release publishes a CycloneDX 1.5 JSON and SPDX 2.3 JSON Software Bill of Materials (SBOM) and cryptographically signed SLSA provenance attestations.
