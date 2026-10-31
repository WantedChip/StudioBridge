# Changelog

All notable changes to StudioBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-31

### Added
- **Local HTTP REST Server & Streamable HTTP Transport:**
  - Added `sbridge serve` CLI command running on loopback (`127.0.0.1`) with constant-time Bearer token verification matching `%LOCALAPPDATA%\studiobridge\broker.token`.
  - Added REST endpoints for DAW inspection and control: `GET /v1/status`, `GET /v1/capabilities`, `GET /v1/mixer`, `POST /v1/mixer/{track}/volume`, `POST /v1/transport/{cmd}`.
  - Added automated OpenAPI 3.1.0 schema generator available at `/openapi.json`.
  - Added Streamable HTTP MCP JSON-RPC 2.0 transport over `POST /mcp` with Server-Sent Events (SSE) support.
  - Added origin, referer, and host validation defending against DNS rebinding and cross-site request forgery attacks.
- **Claude Desktop MCPB Bundle Packaging:**
  - Added MCPB bundle specification descriptor (`mcpb/manifest.json`) declaring package metadata, runtime constraints, and static tool discovery definitions for 42 registered tools.
  - Added pure-Python generated 256x256 RGBA PNG icon asset (`mcpb/icon.png`) with zero graphics dependencies.
  - Added stdio-disciplined launcher wrapper (`mcpb/launcher.py`) routing diagnostics cleanly to stderr.
  - Added bundle build and verification script (`tools/build_mcpb.py`) producing validated `.mcpb` zip archives with SHA-256 integrity checksums.
- **Cloudflare Edge Deployment Pipeline:**
  - Added production Cloudflare Workers static asset configuration (`site/wrangler.jsonc`) with `nodejs_compat`.
  - Injected edge security and caching headers (`site/public/_headers`): HSTS, `X-Content-Type-Options: nosniff`, frame denial, strict CSP, and immutable asset caching.
  - Added canonical documentation and community vanity redirects (`site/public/_redirects`).
  - Added automated live edge and static distribution smoke test suite (`tests/web/test_live_deploy.py`).
- **ARM64 Native Toolchain & Differential Tests:**
  - Added PowerShell 7 ARM64/x64 toolchain diagnostic check (`tools/dev/check-arm64-toolchain.ps1`) inspecting MSVC ARM64 tools, Clang/LLVM, Windows 11 SDK, Rust, and Windows MIDI Services.
  - Added dual-architecture compiler script (`tools/build/build_native.ps1`) targeting ARM64 and x64 PE binaries with graceful fallback.
  - Added optional native acceleration C library (`src/native/`) and transparent ctypes dynamic loader (`studiobridge.wire.native_accel`).
  - Added differential testing suite (`tests/native/test_differential.py`) asserting 100% bit-exact parity between native routines and pure-Python references across CRC-16, CRC-32, septet pack/unpack, SysEx frames, and tolerance comparisons.
- **Security Review & Path Traversal Containment:**
  - Added automated security audit gate tool (`tools/security_audit.py`) validating all 7 pre-release security criteria: HMAC signatures, loopback binding timeouts, secret redaction, path traversal allowlists, prompt injection markers, raw exec elimination, and dependency pinning.
  - Hardened path traversal defenses (`studiobridge.core.paths.validate_safe_path`) with checks for embedded null bytes, URL-encoded sequences, directory escapes (`..`), and UNC paths.
  - Added automated masking for private user profile paths (`studiobridge.core.logging.redact_string`).
  - Added dedicated security unit test suites for path traversal and secret redaction (`tests/unit/security/`).
- **Documentation Content & Compatibility Table Generator:**
  - Added automated compatibility matrix builder (`tools/generate_compat.py`) ingesting diagnostic fixtures and outputting `compat.json` and Markdown tables.
  - Seeded authentic diagnostic bundles for Machine A (ARM64 Snapdragon X Elite), Machine B (x64 Ryzen 9 7950X), and community submissions.
  - Added comprehensive setup guides for all Tier-1 coding agents (Claude Desktop, Cursor, Windsurf, Copilot, Cline, Codex, Antigravity) and Python SDK recipes.
  - Added complete troubleshooting directory covering all 26 doctor checks (`D-ENV-01` through `D-SEC-01`, plus `D-BRK-01`).
  - Added documentation example verification test suite (`tests/unit/docs/test_doc_examples.py`).
- **Multi-Turn Agent Evaluation Suite Expansion:**
  - Expanded scenario library to 21 realistic scripted multi-turn production workflows across mixer balancing, transport lifecycle, note injection, chord sequencing, drum programming, offline FLP mutations, headless rendering, safety challenges, rollback verification, doctor diagnostics, and prompt injection defense.
  - Added evaluation telemetry and reporting engine (`tests/agent_evals/reporter.py`) generating structured JSON and Markdown evaluation reports.
  - Added automated evaluation test runner (`tests/agent_evals/test_suite.py`) asserting 100% scenario pass rate.
- **Software Bill of Materials (SBOM) & Release Provenance:**
  - Added multi-format SBOM generator (`tools/generate_sbom.py`) producing compliant CycloneDX 1.5 JSON and SPDX 2.3 JSON documents with runtime dependency closure isolation.
  - Added GitHub Actions provenance attestation workflow (`.github/workflows/attestations.yml`) integrating `actions/attest-build-provenance` for signed SLSA Level 2+ / Level 3 attestations.
  - Added human-executed deployment runbook detailing step-by-step publishing sequences, OIDC trusted publishing, and emergency rollback procedures.

---

## [0.6.0] - 2026-10-26

### Added
- Official documentation and landing page site built with Astro Starlight.
- Interactive Signal-Path hero diagram with live SysEx hex frame inspection.
- Capability matrix explorer for Windows ARM64 and x64 hardware platforms.
- Interactive console demo island showcasing authentic session transcripts.
- Complete API reference integration covering all 8 FL Studio controller scripting modules.
- Generative Engine Optimization (GEO) context compiler producing `site/public/llms.txt` and `site/public/llms-full.txt`.
- OpenGraph and Twitter social card generator producing `og.svg` and `og.png`.
- Automated web quality audit suite covering Lighthouse thresholds, WCAG 2.2 AA accessibility, visual regression, and bundle size budgets.

---

## [0.5.0] - 2026-10-25

### Added
- Pure-Python binary FLP project parser and AST-level mutation engine.
- FL Studio 21 through 26 format profile decoders and version resolvers.
- Lossless AST round-trip serialization with structural invariant verification.
- High-level object model for project metadata, channels, patterns, and mixer routing.
- Seed template instantiation CLI (`sbridge flp template add`).
- Offline FLP Model Context Protocol (MCP) tool suite.

---

## [0.4.0] - 2026-10-24

### Added
- Win32 UI actuator with foreground window verification and modal dialog detection.
- Focus-guarded Piano Roll generator script execution with automatic cursor restoration.
- Piano roll oracle verification using note read-back SHA-256 hash comparison.
- Headless render supervisor launching `FL64.exe` child processes with timeout guards.
- Acoustic signal validator reporting WAV sample rates, true peak dBFS, and RMS energy metrics.
- Piano roll and headless render Model Context Protocol (MCP) tool suites.

---

## [0.3.0] - 2026-10-23

### Added
- Model Context Protocol (MCP) server exposing DAW inspection, live control, and safety tools.
- Static tool discovery metadata for 42 registered MCP tools across 5 toolsets.
- Agent installation engine with templated configuration generators for 10 coding assistants.
- Agent skill bundles and scripted evaluation test harness.
- NPM launcher wrapper package (`@studiobridge/mcp`) for zero-install execution via `npx`.

---

## [0.2.0] - 2026-10-22

### Added
- Strictly typed Python SDK wrapping FL Studio controller namespaces (`transport`, `mixer`, `channels`, `patterns`, `plugins`, `project`, `ui`, `notes`).
- Verified write engine with automatic read-back comparison against target values within configurable tolerances.
- Safety interlock system (`READ_ONLY`, `PROMPT`, `PERMISSIVE`) with confirmation challenge tokens.
- Append-only mutation journal assigning monotonic mutation IDs (`MID`) and rollback snapshots.
- Transactions with automatic state rollback on unhandled exceptions.
- Clean-room scripting API manifest scraper, normalizer, and drift detection CI.

---

## [0.1.0] - 2026-10-21

### Added
- Foundation monorepo scaffold using `uv`, `ruff`, `pyright`, and `pytest`.
- Bidirectional MIDI System Exclusive (SysEx) wire protocol with CRC-16 CCITT validation.
- Pure-Python ctypes WinMM virtual MIDI backend with zero native dependencies on Windows.
- Windows MIDI Services (WMS) loopback support for Windows 11 Build 26100+.
- Setup doctor CLI (`sbridge doctor`) running automated checks across 26 diagnostic points.
- Sandboxed Python 3.9 FL Studio controller script (`device_sbridge.py`) and local emulator.
- Local broker daemon with request scheduling and connection management.
- Brand token management and rename tooling.
