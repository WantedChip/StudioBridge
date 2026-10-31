# Doctor Check Directory & Troubleshooting Guide

The `sbridge doctor` diagnostic engine runs automated health checks across your environment, port topology, controller script integrity, and wire communication.

This directory provides authoritative explanations, root cause analysis, and recovery steps for all diagnostic checks.

---

## Quick Reference Table

| Check ID | Severity | Requires FL | Check Name | Primary Scope |
| :--- | :--- | :---: | :--- | :--- |
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
- **Failure Mode:** Informational flag indicating whether Python is executing natively or via Prism x64 emulation on ARM64.
- **Recovery Steps:** No recovery needed. For optimal latency on Snapdragon X hardware, install native ARM64 Python (`win_arm64`).

---

## FL Studio Discovery Checks (`D-FL-*`)

### `D-FL-01`
- **Name:** FL Studio Installation Discovery
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** FL Studio executable (`FL64.exe`) cannot be located in standard paths or the Windows registry.
- **Root Causes:**
  - FL Studio is installed in a non-standard path.
  - Registry keys (`HKCU\Software\Image-Line\FL Studio`) are missing.
- **Recovery Steps:**
  1. Set the environment variable pointing to your FL Studio installation:
     ```powershell
     [System.Environment]::SetEnvironmentVariable("FL_STUDIO_PATH", "C:\Path\To\FL Studio", "User")
     ```
  2. Re-run `sbridge doctor`.

### `D-FL-02`
- **Name:** FL Studio Process Status
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** FL Studio is not currently running.
- **Recovery Steps:** Launch FL Studio before running live wire checks.

### `D-FL-03`
- **Name:** FL Studio MIDI Scripting Support
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Discovered FL Studio version is older than FL 20.7 (which first introduced Python MIDI scripting).
- **Recovery Steps:** Upgrade to FL Studio 21.2+ or 24.1+.

---

## MIDI Port Topology Checks (`D-PORT-*`)

### `D-PORT-01`
- **Name:** Windows MIDI Services (`midisrv`) Status
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Windows MIDI Services (`midisrv`) service is stopped or not installed.
- **Recovery Steps:**
  ```powershell
  Start-Service -Name "midisrv"
  ```

### `D-PORT-02`
- **Name:** Microsoft MIDI Tools (`midi.exe`) Availability
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** `midi.exe` CLI is not found on system PATH.
- **Recovery Steps:** Install the Windows MIDI Services developer tools package from Microsoft.

### `D-PORT-03`
- **Name:** WinMM Bidirectional Loopback Visibility
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Neither input nor output loopback ports are visible to the WinMM subsystem.
- **Recovery Steps:**
  ```powershell
  sbridge setup loopback
  ```

### `D-PORT-04`
- **Name:** MIDI Port Name Length Discipline
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Virtual port name exceeds 31 characters, risking truncation by the legacy WinMM 32-character buffer boundary.
- **Recovery Steps:** Use standard port names: `StudioBridge In` (14 chars) and `StudioBridge Out` (15 chars).

### `D-PORT-05`
- **Name:** MIDI Port Exclusive Open Conflicts
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Another process has opened the MIDI port in exclusive mode.
- **Recovery Steps:**
  1. Identify processes holding MIDI handles.
  2. Close any orphaned background Python or DAW processes holding the port.

### `D-PORT-06`
- **Name:** loopMIDI Driver Availability
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** Reports whether the loopMIDI driver is active as a fallback.

### `D-PORT-07`
- **Name:** Loopback Endpoint Pair Presence
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** Exactly one half of the bidirectional pair was discovered (e.g. `StudioBridge In` exists, but `StudioBridge Out` is missing).
- **Recovery Steps:**
  ```powershell
  sbridge setup loopback --recreate
  ```

---

## Device Script & Wire Checks (`D-DEV-*`, `D-WIRE-*`, `D-SBX-*`)

### `D-DEV-01`
- **Name:** Device Script Asset Presence and Integrity
- **Severity:** `error`
- **Requires FL Studio:** No
- **Failure Mode:** `device_sbridge.py` is missing or corrupted in the FL Studio Hardware user directory.
- **Recovery Steps:**
  ```powershell
  sbridge setup install
  ```

### `D-DEV-02`
- **Name:** Device Script Build ID Synchronization
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** The installed `device_sbridge.py` script version is out of sync with the active Python package.
- **Recovery Steps:**
  ```powershell
  sbridge setup install --force
  ```

### `D-DEV-03`
- **Name:** FL Studio MIDI Settings Binding (Hello Handshake)
- **Severity:** `error`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** FL Studio is running, but no response was received to the SysEx `hello` handshake within 2.0 seconds.
- **Recovery Steps:**
  1. In FL Studio, press <kbd>F10</kbd> to open **MIDI Settings**.
  2. Ensure `StudioBridge Out` is assigned controller type `StudioBridge` on **Port 10**.
  3. Ensure `StudioBridge In` is enabled on **Port 10**.

### `D-WIRE-01`
- **Name:** Wire Round-Trip Latency
- **Severity:** `warn`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** Measured loopback round-trip latency exceeds 10 ms.
- **Recovery Steps:**
  - Switch to native Windows MIDI Services loopback.
  - Lower the audio buffer size in FL Studio Audio Settings to reduce UI scheduling jitter.

### `D-WIRE-02`
- **Name:** Wire Protocol Error and Retry Rate
- **Severity:** `warn`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** CRC mismatches or dropped frames exceeded the 1.0% tolerance threshold during diagnostic burst tests.
- **Recovery Steps:** Check for port congestion or conflicting MIDI applications sending non-SysEx messages on Port 10.

### `D-SBX-01`
- **Name:** FL Studio Controller Script Sandbox Capabilities
- **Severity:** `info`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** Lists supported live scripting modules (`mixer`, `transport`, `channels`, `patterns`, `plugins`, `ui`, `general`).

---

## Actuation, Render, FLP & Agent Checks (`D-PR-*`, `D-ACT-*`, `D-RND-*`, `D-FLP-*`, `D-AGT-*`, `D-SEC-*`, `D-BRK-*`)

### `D-PR-01`
- **Name:** Piano Roll Scripts Installation
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Helper scripts in `%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Piano roll scripts\` are missing.
- **Recovery Steps:**
  ```powershell
  sbridge setup install
  ```

### `D-ACT-01`
- **Name:** UI Actuator Window and Modal State
- **Severity:** `warn`
- **Requires FL Studio:** **Yes**
- **Failure Mode:** FL Studio has a blocking modal dialog open (e.g. Save As, Plugin Error).
- **Recovery Steps:** Dismiss any open dialog windows inside FL Studio.

### `D-RND-01`
- **Name:** Headless Render Executable Availability
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** `FL64.exe` is not executable or command line export is not permitted.

### `D-FLP-01`
- **Name:** Offline FLP Engine Profile Compatibility
- **Severity:** `info`
- **Requires FL Studio:** No
- **Failure Mode:** Verifies offline parsing profiles across FL 21, FL 24, FL 25, and FL 26 formats.

### `D-AGT-01`
- **Name:** AI Agent Adapters Configuration
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Discovers installed AI agent configuration files (Claude Desktop, Cursor, Windsurf, Copilot, Cline, etc.) and flags missing MCP configurations.
- **Recovery Steps:** Follow the [Quickstart Guide](quickstart.md) for your specific agent.

### `D-SEC-01`
- **Name:** Authentication Token and Secret ACL Security
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Permissions on `%LOCALAPPDATA%\studiobridge\broker.token` are overly permissive.
- **Recovery Steps:**
  ```powershell
  icacls "$env:LOCALAPPDATA\studiobridge\broker.token" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
  ```

### `D-BRK-01`
- **Name:** Local Broker Daemon Reachability
- **Severity:** `warn`
- **Requires FL Studio:** No
- **Failure Mode:** Background broker daemon is not responding on `127.0.0.1`.
- **Recovery Steps:**
  ```powershell
  sbridge broker restart
  ```
