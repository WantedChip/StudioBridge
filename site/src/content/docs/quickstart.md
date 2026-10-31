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

### GitHub Copilot

Configure the StudioBridge MCP server in VS Code for GitHub Copilot Chat by editing `.vscode/mcp.json` or your global user settings:

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

### Cline

Configure the StudioBridge MCP server in Cline (VS Code extension) by editing `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`:

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

### Python SDK Quickstart

StudioBridge provides a fully-typed Python SDK for programmatic DAW automation and script execution:

```python
from studiobridge import Studio

# Connect to the local DAW session
with Studio.connect() as studio:
    # Query transport state
    is_playing = studio.transport.is_playing()
    print(f"Transport playing: {is_playing}")

    # Query master mixer track volume (track index 0)
    master_vol = studio.mixer.get_volume(0)
    print(f"Master volume: {master_vol:.2f}")
```

For asynchronous automation pipelines (such as background event monitors or async web servers), use `AsyncStudio`:

```python
import asyncio
from studiobridge import AsyncStudio


async def main() -> None:
    async with AsyncStudio.connect() as studio:
        tempo = await studio.transport.get_tempo()
        print(f"Current tempo: {tempo} BPM")


asyncio.run(main())
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

If any check fails, refer to the [Doctor Check Directory](/docs/troubleshooting/doctor-checks/) for exact recovery commands.
