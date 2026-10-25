---
title: "Quickstart Guide"
description: "Step-by-step installation and configuration guide for StudioBridge across all supported AI coding agents and IDEs."
---

This guide walks you through connecting your AI coding agent to FL Studio in under five minutes.

StudioBridge operates locally with zero kernel drivers, zero native compiled C dependencies, and zero telemetry.

---

## 1. Prerequisites Verification

Before starting, verify your system meets the minimum requirements:

| Component | Minimum Requirement | Recommended | Verification Command |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 10 64-bit (Build 19041+) | Windows 11 Build 26100+ (WMS) | `[System.Environment]::OSVersion.Version` |
| **Architecture** | Windows x64 or Windows on ARM64 | ARM64 (Snapdragon X) or x64 | `[System.Environment]::Is64BitOperatingSystem` |
| **Python** | Python 3.10+ | Python 3.12+ (pure Python) | `python --version` |
| **FL Studio** | FL Studio 21.2+ (API v40+) | FL Studio 24.1+ (API v44+) | Open FL Studio → Help → About |
| **MIDI Loopback** | Windows MIDI Services (WMS) or loopMIDI | Windows MIDI Services loopback | `sbridge doctor` |

---

## 2. Installation Steps

### Step 1: Install StudioBridge CLI & MCP Server

Install StudioBridge into your global Python environment or run via `uvx`:

```bash
# Recommended: Install via uv
uv tool install studiobridge

# Alternative: Install via pip
pip install --upgrade studiobridge
```

Verify the CLI is accessible:
```bash
sbridge --version
```

### Step 2: Configure Virtual MIDI Loopback

StudioBridge communicates with FL Studio via a bidirectional MIDI loopback pair:

```bash
# Automatically create or verify the loopback endpoints:
sbridge setup loopback
```

> **Windows 11 (Build 26100+):** StudioBridge automatically uses native Windows MIDI Services (`midisrv`) loopback endpoints (`StudioBridge In` / `StudioBridge Out`). Zero third-party drivers are required.
>
> **Windows 10:** If Windows MIDI Services is not installed, StudioBridge will detect any existing WinMM loopback driver (e.g. `loopMIDI`) and route through it seamlessly.

### Step 3: Install FL Studio Controller Script

Install the sandboxed Python controller script into your FL Studio user hardware directory:

```bash
sbridge setup install
```

This copies `device_sbridge.py` into:
```
%USERPROFILE%\Documents\Image-Line\FL Studio\Settings\Hardware\StudioBridge\
```

### Step 4: Configure FL Studio MIDI Settings

1. Open **FL Studio**.
2. Press <kbd>F10</kbd> to open **MIDI Settings**.
3. Under **Output**:
   - Select `StudioBridge In` (or your loopback input port).
   - Set **Port** to `10`.
   - Enable **Send master sync** if desired.
4. Under **Input**:
   - Select `StudioBridge Out` (or your loopback output port).
   - Set **Controller type** to `StudioBridge`.
   - Set **Port** to `10`.
   - Enable the port.
5. In the FL Studio status bar, you will see `StudioBridge controller connected`.

---

## 3. Agent & IDE Configuration

StudioBridge provides standard Model Context Protocol (MCP) server endpoints. Configure your preferred coding agent below:

### Claude Code

Add the StudioBridge MCP server directly using the `claude` CLI:

```bash
claude mcp add studiobridge -- uvx studiobridge mcp
```

Or configure in your project's `.claude/config.json`:
```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Cursor

Open **Cursor Settings** → **Features** → **MCP Servers** → **Add New MCP Server**, or edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Codex

Configure in `~/.codex/config.toml`:

```toml
[mcp_servers.studiobridge]
command = "uvx"
args = ["studiobridge", "mcp"]
```

### Antigravity

Configure in `~/.antigravity/mcp_servers.json` or your project workspace config:

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Gemini CLI

Configure in `~/.gemini/mcp_servers.json`:

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Windsurf

Configure in `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Zed

Configure in `%APPDATA%\Zed\settings.json`:

```json
{
  "context_servers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### VS Code (with Cline / Roo Code / MCP extension)

Configure in `.vscode/settings.json`:

```json
{
  "mcp.servers": {
    "studiobridge": {
      "command": "uvx",
      "args": ["studiobridge", "mcp"]
    }
  }
}
```

### Plain CLI

You do not need an AI agent to use StudioBridge. Control FL Studio directly from your terminal:

```bash
# Query playback state
sbridge call transport.isPlaying

# Start playback
sbridge call transport.start

# Stop playback
sbridge call transport.stop

# Get volume of Master mixer track (index 0)
sbridge call mixer.getTrackVolume --args '{"track": 0}'

# Inspect mutation journal
sbridge journal list
```

---

## 4. Health Check Verification

Run the diagnostics doctor to ensure all subsystems and ports are operational:

```bash
sbridge doctor
```

A healthy diagnostic report will look like this:

```
StudioBridge Doctor Report (2026-10-26T00:00:00Z)
FL Studio Running: Yes
==============================================================================
Status   ID          Severity  Check Name
------------------------------------------------------------------------------
[PASS]   D-ENV-01    error     Python Version and Architecture (3.12.2 / ARM64)
[PASS]   D-ENV-02    warn      Windows OS Build for Windows MIDI Services (Build 26100)
[PASS]   D-ENV-03    info      Python Emulation Status (Native ARM64)
[PASS]   D-FL-01     error     FL Studio Installation Discovery (24.1.0)
[PASS]   D-FL-02     info      FL Studio Process Status (FL64.exe running)
[PASS]   D-PORT-01   warn      Windows MIDI Services (midisrv) Status (Running)
[PASS]   D-PORT-03   error     WinMM Bidirectional Loopback Visibility
[PASS]   D-DEV-01    error     Device Script Asset Presence and Integrity
[PASS]   D-DEV-02    warn      Device Script Build ID Synchronization
[PASS]   D-DEV-03    error     FL Studio MIDI Settings Binding (hello handshake)
[PASS]   D-WIRE-01   warn      Wire Round-Trip Latency (p50: 1.8ms / p95: 3.4ms)
------------------------------------------------------------------------------
Passed: 11 | Failed: 0 | Warned: 0 | Skipped: 0
```

If any check fails, refer to the [Doctor Check Directory](/docs/troubleshooting/doctor-checks/) for exact recovery commands.

---

## 5. Safety Modes & Mutation Journal

StudioBridge enforces strict safety interlocks to protect your creative projects:

1. **Read-Only Session Default:** Agents start in read-only mode. Queries like `transport.isPlaying` or `mixer.getTrackVolume` execute without restriction, while mutating calls require explicit session authorization.
2. **Read-Back Verification:** Every mutating write (e.g. setting track volume or tempo) is read back from the FL engine and compared against the target value before reporting success.
3. **Mutation Journal:** Every change is recorded in an append-only JSON journal (`~/.studiobridge/journal/`).
4. **Instant Rollback:** Revert changes with one command:
   ```bash
   sbridge journal rollback --last 1
   ```
