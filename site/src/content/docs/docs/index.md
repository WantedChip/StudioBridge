---
title: "StudioBridge Documentation"
description: "Authoritative technical guides, architecture specifications, API reference, and troubleshooting directory for StudioBridge."
---

Welcome to the **StudioBridge Documentation**.

StudioBridge patches AI coding agents (Claude Code, Cursor, Codex, Antigravity, Gemini, Windsurf, Zed, VS Code) directly into FL Studio for verified, reversible, and local DAW automation.

---

## Documentation Sections

### 1. [Getting Started](/docs/getting-started/quickstart/)
Complete walkthroughs for connecting your preferred agent or IDE in under five minutes.
- [Prerequisites & Verification](/docs/getting-started/quickstart/#1-prerequisites-verification)
- [Loopback Setup & Script Installation](/docs/getting-started/quickstart/#2-installation-steps)
- [Agent & IDE Configurations](/docs/getting-started/quickstart/#3-agent--ide-configuration) (Claude, Cursor, Codex, Windsurf, Zed, VS Code, CLI)
- [Doctor Health Checks & Verification](/docs/getting-started/quickstart/#4-health-check-verification)
- [Safety Modes & Mutation Journal](/docs/getting-started/quickstart/#5-safety-modes--mutation-journal)

### 2. Architecture Guides
Deep dive into the underlying engineering, protocols, and control surfaces:
- **[Control Planes Architecture](/docs/architecture/control-planes/):** Detailed breakdown of the four control planes: Live MIDI RPC, Offline FLP Engine, Headless Render Supervisor, and Win32 UI Actuation.
- **[SysEx Wire Protocol Specification](/docs/architecture/wire-protocol/):** Complete framing specification, 7-to-8 bit payload packing, CRC-16 CCITT validation, chunk reassembly, and opcode directories.

### 3. [Troubleshooting & Doctor Checks](/docs/troubleshooting/doctor-checks/)
Comprehensive directory mapping every diagnostic code (`D-ENV-*`, `D-FL-*`, `D-PORT-*`, `D-DEV-*`, `D-WIRE-*`, `D-SBX-*`, `D-PR-*`, `D-ACT-*`, `D-RND-*`, `D-FLP-*`, `D-AGT-*`, `D-SEC-*`, `D-BRK-*`) to exact root causes and remediation commands.

### 4. [FL Studio API Reference](/docs/api/)
Authoritative reference documentation for all 119 functions across the 8 normalized Python API modules (API v44):
- [channels — Channel Rack & Generators](/docs/api/channels/)
- [device — Hardware Controller & Surface](/docs/api/device/)
- [general — General FL Studio DAW Engine](/docs/api/general/)
- [mixer — Mixer Tracks, Routing & Volume](/docs/api/mixer/)
- [patterns — Patterns, Clips & Sequencer](/docs/api/patterns/)
- [plugins — Plugin Parameters & VST/AU](/docs/api/plugins/)
- [transport — Transport, Playback & Recording](/docs/api/transport/)
- [ui — User Interface Windows & Focus](/docs/api/ui/)

---

## Core Tenets

1. **Zero Native Compiled Dependencies on Windows:** Pure-Python runtime with ctypes bindings.
2. **Device Script Sandbox Integrity:** Python 3.9 compatible, no external packages, no socket connections.
3. **Verified, Reversible Writes:** Read-back verification and mutation journal with instant rollback.
4. **Driverless Windows MIDI Services:** Native loopback routing without third-party kernel drivers.
5. **No Telemetry, No Accounts:** Runs entirely local on your machine.
