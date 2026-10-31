---
title: "Doctor Check Directory & Troubleshooting Guide"
description: "Comprehensive diagnostic reference mapping every StudioBridge doctor check code (D-*) to failure modes, root causes, and exact recovery steps."
---

The `sbridge doctor` diagnostic engine runs automated health checks across your environment, port topology, controller script integrity, and wire communication.

This directory provides authoritative explanations, root cause analysis, and recovery steps for all diagnostic checks.

---

## Quick Reference Table

| Check ID | Severity | Requires FL | Check Name | Primary Scope |
| :--- | :--- | :--- | :--- | :--- |
| [`D-ENV-01`](#d-env-01) | `error` | No | Python Version and Architecture | Host runtime compatibility |
| [`D-ENV-02`](#d-env-02) | `warn` | No | Windows OS Build for Windows MIDI Services | Windows MIDI Services support |
| [`D-ENV-03`](#d-env-03) | `info` | No | Python Emulation Status | Native execution architecture |
| [`D-FL-01`](#d-fl-01) | `error` | No | FL Studio Installation Discovery | DAW installation detection |
| [`D-FL-02`](#d-fl-02) | `info` | No | FL Studio Process Status | Active DAW process state |
| [`D-FL-03`](#d-fl-03) | `error` | No | FL Studio MIDI Scripting Support | Python MIDI scripting API |
| [`D-PORT-01`](#d-port-01) | `warn` | No | Windows MIDI Services (midisrv) Status | Windows MIDI Services service |
| [`D-PORT-02`](#d-port-02) | `warn` | No | Microsoft MIDI Tools (midi.exe) Availability | MIDI CLI tooling |
| [`D-PORT-03`](#d-port-03) | `error` | No | WinMM Bidirectional Loopback Visibility | MIDI port loopback detection |
| [`D-PORT-04`](#d-port-04) | `warn` | No | MIDI Port Name Length Discipline (<= 31 chars) | WinMM buffer limits |
| [`D-PORT-05`](#d-port-05) | `error` | No | MIDI Port Exclusive Open Conflicts | Port locking and handle leaks |
| [`D-PORT-06`](#d-port-06) | `info` | No | loopMIDI Driver Availability | Legacy driver fallback |
| [`D-PORT-07`](#d-port-07) | `error` | No | Loopback Endpoint Pair Presence | In/Out endpoint pairs |
| [`D-DEV-01`](#d-dev-01) | `error` | No | Device Script Asset Presence and Integrity | Controller script files |
| [`D-DEV-02`](#d-dev-02) | `warn` | No | Device Script Build ID Synchronization | Script version synchronization |
| [`D-DEV-03`](#d-dev-03) | `error` | **Yes** | FL Studio MIDI Settings Binding (hello handshake) | Live SysEx handshake |
| [`D-WIRE-01`](#d-wire-01) | `warn` | **Yes** | Wire Round-Trip Latency (p50/p95) | Loopback RPC responsiveness |
| [`D-WIRE-02`](#d-wire-02) | `warn` | **Yes** | Wire Protocol Error and Retry Rate | Frame drops and retries |
| [`D-SBX-01`](#d-sbx-01) | `info` | **Yes** | FL Studio Controller Script Sandbox Capabilities | Runtime API discovery |
| [`D-PR-01`](#d-pr-01) | `warn` | No | Piano Roll Scripts Installation | Piano roll script assets |
| [`D-ACT-01`](#d-act-01) | `warn` | **Yes** | UI Actuator Window and Modal State | Window automation & modal dialogs |
| [`D-RND-01`](#d-rnd-01) | `warn` | No | Headless Render Executable (FL64.exe) Availability | Background export binary |
| [`D-FLP-01`](#d-flp-01) | `info` | No | Offline FLP Engine Profile Compatibility | Binary file parsing |
| [`D-AGT-01`](#d-agt-01) | `warn` | No | AI Agent Adapters Configuration | Agent config templates |
| [`D-SEC-01`](#d-sec-01) | `warn` | No | Authentication Token and Secret ACL Security | Token permissions |
| [`D-BRK-01`](#d-brk-01) | `warn` | No | Local Broker Daemon Reachability | Background broker service |

---

## Environment Checks (`D-ENV-*`)

### `D-ENV-01`
- **Name:** Python Version and Architecture
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Python runtime is below 3.10 or running under a 32-bit architecture.
- **Root Causes:**
  - Python 3.9 or older is active in the environment PATH.
  - A 32-bit (x86) Python distribution was installed instead of 64-bit (x64/ARM64).
- **Recovery Steps:**
  1. Install Python 3.12+ (64-bit) from [python.org](https://www.python.org/) or via `winget`:
     ```powershell
     winget install Python.Python.3.12
     ```
  2. Verify:
     ```powershell
     python -c "import sys; print(sys.version, sys.maxsize > 2**32)"
     ```

### `D-ENV-02`
- **Name:** Windows OS Build for Windows MIDI Services
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Windows build is older than Build 26100 (Windows 11 24H2).
- **Root Causes:**
  - Running Windows 10 or an earlier build of Windows 11 without native Windows MIDI Services.
- **Recovery Steps:**
  1. Update to Windows 11 Build 26100+ for native driverless MIDI loopback.
  2. If remaining on Windows 10/11 older builds, install a virtual MIDI driver:
     ```powershell
     winget install TobiasErichsen.loopMIDI
     ```

### `D-ENV-03`
- **Name:** Python Emulation Status
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** Python is running under x64 emulation on Windows on ARM64 instead of native ARM64.
- **Root Causes:**
  - An x64 Python binary was installed on a Qualcomm Snapdragon X Elite machine.
- **Recovery Steps:**
  1. Install native Windows on ARM64 Python:
     ```powershell
     winget install Python.Python.3.12 --architecture arm64
     ```

---

## FL Studio Host Checks (`D-FL-*`)

### `D-FL-01`
- **Name:** FL Studio Installation Discovery
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** No valid FL Studio installation detected in standard Program Files directories.
- **Root Causes:**
  - FL Studio is not installed or was installed to a non-standard custom path.
- **Recovery Steps:**
  1. If FL Studio is installed to a custom directory, set `FL_INSTALL_DIR`:
     ```powershell
     [System.Environment]::SetEnvironmentVariable("FL_INSTALL_DIR", "D:\DAWs\FL Studio", "User")
     ```
  2. Verify installation with `sbridge doctor`.

### `D-FL-02`
- **Name:** FL Studio Process Status
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** `FL64.exe` is not currently running.
- **Root Causes:**
  - FL Studio is closed. Live checks will be gracefully skipped per `[DOC-01]`.
- **Recovery Steps:**
  1. Launch FL Studio if you want to run live MIDI RPC checks.

### `D-FL-03`
- **Name:** FL Studio MIDI Scripting Support
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Detected FL Studio version is older than 20.7 (API version < 1).
- **Root Causes:**
  - Legacy FL Studio installation lacking the Python MIDI controller scripting engine.
- **Recovery Steps:**
  1. Update FL Studio to version 21.2+ or 24.1+.

---

## MIDI Port Topology Checks (`D-PORT-*`)

### `D-PORT-01`
- **Name:** Windows MIDI Services (midisrv) Status
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Windows MIDI Services service (`midisrv`) is stopped or disabled.
- **Root Causes:**
  - The `midisrv` background service failed to start or was stopped by user.
- **Recovery Steps:**
  1. Start the service via PowerShell (Administrator):
     ```powershell
     Start-Service midisrv
     ```

### `D-PORT-02`
- **Name:** Microsoft MIDI Tools (midi.exe) Availability
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** `midi.exe` CLI tool is not found on system PATH.
- **Root Causes:**
  - Windows MIDI Services SDK tools are not installed or PATH is missing the binary directory.
- **Recovery Steps:**
  1. Install Microsoft MIDI Services developer tools or run `sbridge setup loopback` to configure automatically.

### `D-PORT-03`
- **Name:** WinMM Bidirectional Loopback Visibility
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** No loopback pair visible to the WinMM MIDI subsystem.
- **Root Causes:**
  - Virtual MIDI endpoints have not been created yet.
- **Recovery Steps:**
  1. Run the automatic setup command:
     ```powershell
     sbridge setup loopback
     ```

### `D-PORT-04`
- **Name:** MIDI Port Name Length Discipline (<= 31 chars)
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** A virtual MIDI port name exceeds 31 characters.
- **Root Causes:**
  - WinMM APIs truncate port names longer than 31 characters (`MAXPNAMELEN - 1`), causing mismatch in FL Studio device dropdowns.
- **Recovery Steps:**
  1. Re-create loopback ports using standard names (`StudioBridge In` / `StudioBridge Out`).

### `D-PORT-05`
- **Name:** MIDI Port Exclusive Open Conflicts
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** A process has opened the MIDI port in exclusive mode, preventing StudioBridge from connecting.
- **Root Causes:**
  - Another DAW, MIDI monitor, or zombie background process holds an exclusive lock on the port.
- **Recovery Steps:**
  1. Close any conflicting MIDI software (e.g. MIDI-OX, other DAWs).
  2. Kill any stale StudioBridge processes:
     ```powershell
     Stop-Process -Name "sbridge", "python" -Force -ErrorAction SilentlyContinue
     ```

### `D-PORT-06`
- **Name:** loopMIDI Driver Availability
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** loopMIDI driver is not installed.
- **Root Causes:**
  - Normal on Windows 11 Build 26100+ using Windows MIDI Services. Only relevant if WMS is unavailable.
- **Recovery Steps:**
  1. No action required if Windows MIDI Services is functioning.

### `D-PORT-07`
- **Name:** Loopback Endpoint Pair Presence
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Only an input or output port was detected, but not a matching bidirectional pair.
- **Root Causes:**
  - One side of the virtual MIDI loopback pair was deleted or not initialized.
- **Recovery Steps:**
  1. Re-run:
     ```powershell
     sbridge setup loopback --force
     ```

---

## Device Script Checks (`D-DEV-*`)

### `D-DEV-01`
- **Name:** Device Script Asset Presence and Integrity
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** `device_sbridge.py` missing from FL Studio Hardware Settings directory.
- **Root Causes:**
  - Script was never installed or FL Studio user data folder was relocated.
- **Recovery Steps:**
  1. Run the script installer:
     ```powershell
     sbridge setup install
     ```

### `D-DEV-02`
- **Name:** Device Script Build ID Synchronization
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Installed script version does not match the active `studiobridge` library version.
- **Root Causes:**
  - `studiobridge` package was upgraded without updating the FL Studio script assets.
- **Recovery Steps:**
  1. Re-sync script assets:
     ```powershell
     sbridge setup install --overwrite
     ```

### `D-DEV-03`
- **Name:** FL Studio MIDI Settings Binding (hello handshake)
- **Severity:** `error`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** StudioBridge sent a `HELLO` SysEx probe but received no response from FL Studio.
- **Root Causes:**
  - FL Studio MIDI settings have not assigned Controller Type "StudioBridge" to the loopback port.
  - The input or output port is disabled in FL Studio MIDI Settings (<kbd>F10</kbd>).
  - Port numbers do not match (e.g. Input is Port 10 but Output is Port 0).
- **Recovery Steps:**
  1. Open FL Studio → <kbd>F10</kbd> (MIDI Settings).
  2. Set Output: `StudioBridge In` → Port `10` → Enable.
  3. Set Input: `StudioBridge Out` → Controller type `StudioBridge` → Port `10` → Enable.

---

## Wire Communication Checks (`D-WIRE-*`)

### `D-WIRE-01`
- **Name:** Wire Round-Trip Latency (p50/p95)
- **Severity:** `warn`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** Round-trip latency across the loopback connection exceeds the 10ms threshold.
- **Root Causes:**
  - Heavy CPU load or high audio buffer size in FL Studio delaying the UI message pump.
- **Recovery Steps:**
  1. Verify FL Studio audio buffer is set to a reasonable size (e.g. 256 or 512 samples).
  2. Close background CPU-intensive processes.

### `D-WIRE-02`
- **Name:** Wire Protocol Error and Retry Rate
- **Severity:** `warn`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** Packet retry rate exceeds 2% or CRC mismatches were detected.
- **Root Causes:**
  - Corrupted buffer in virtual MIDI driver or buffer overflow.
- **Recovery Steps:**
  1. Restart virtual MIDI loopback service or reset the bridge session.

---

## Sandbox & Specialized Checks (`D-SBX-*`, `D-PR-*`, `D-ACT-*`, `D-RND-*`, `D-FLP-*`, `D-AGT-*`, `D-SEC-*`, `D-BRK-*`)

### `D-SBX-01`
- **Name:** FL Studio Controller Script Sandbox Capabilities
- **Severity:** `info`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** One or more optional FL Studio API modules are missing.
- **Root Causes:**
  - Older FL Studio API versions omit certain modules (e.g. `plugins` or `patterns` in pre-20.9).
- **Recovery Steps:**
  1. Check the [Capability Matrix](/compat) for version-specific feature availability.

### `D-PR-01`
- **Name:** Piano Roll Scripts Installation
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** StudioBridge piano roll helper scripts are missing from the FL User Data folder.
- **Root Causes:**
  - Piano roll scripts were not installed during initial setup.
- **Recovery Steps:**
  1. Install piano roll scripts:
     ```powershell
     sbridge setup install --piano-roll
     ```

### `D-ACT-01`
- **Name:** UI Actuator Window and Modal State
- **Severity:** `warn`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** FL Studio is blocked by an unhandled modal dialogue (e.g. missing plugin prompt).
- **Root Causes:**
  - An alert dialog is preventing the main window from processing messages.
- **Recovery Steps:**
  1. Switch to FL Studio and dismiss the open dialogue, or run:
     ```powershell
     sbridge actuate dismiss-modals
     ```

### `D-RND-01`
- **Name:** Headless Render Executable (FL64.exe) Availability
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Headless export executable cannot be located.
- **Root Causes:**
  - `FL64.exe` is missing from the discovered installation folder.
- **Recovery Steps:**
  1. Verify the FL Studio installation integrity.
  2. If FL Studio is in a custom path, configure `FL_INSTALL_DIR`.

### `D-FLP-01`
- **Name:** Offline FLP Engine Profile Compatibility
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** Offline FLP parser encountered an unrecognized project version chunk.
- **Root Causes:**
  - A newer, unverified FL Studio project format was encountered.
- **Recovery Steps:**
  1. Update `studiobridge` to the latest release for updated format specifications.
  2. Inspect the project file headers with `sbridge flp inspect <file.flp>`.

### `D-AGT-01`
- **Name:** AI Agent Adapters Configuration
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** No MCP configuration found for installed coding agents (Cursor, Claude, VS Code, etc.).
- **Root Causes:**
  - The agent was installed after StudioBridge was set up.
- **Recovery Steps:**
  1. Refer to the [Quickstart Guide](/docs/getting-started/quickstart/) to paste the MCP configuration into your agent's config file.

### `D-SEC-01`
- **Name:** Authentication Token and Secret ACL Security
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Authentication token file permissions are overly permissive.
- **Root Causes:**
  - File ACLs in `~/.studiobridge/` allow read access by other local users.
- **Recovery Steps:**
  1. Restrict ACL permissions:
     ```powershell
     icacls "$HOME\.studiobridge" /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F"
     ```

### `D-BRK-01`
- **Name:** Local Broker Daemon Reachability
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Local broker daemon is not responding to health probes.
- **Root Causes:**
  - Daemon was not started or crashed due to port collision.
- **Recovery Steps:**
  1. Restart daemon:
     ```powershell
     sbridge daemon restart
     ```
