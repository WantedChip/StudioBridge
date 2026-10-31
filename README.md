<div align="center">

# 🎛️ StudioBridge
<!-- mcp-name: io.github.wantedchip/studiobridge -->

**The Local-First AI Agent & Automation Bridge for Image-Line FL Studio**

Connect modern AI coding assistants and Python scripts directly to your DAW with sub-millisecond bidirectional MIDI SysEx RPC, zero kernel drivers, and an offline FLP binary engine.

[![CI](https://img.shields.io/badge/CI-Passing-brightgreen?logo=github-actions&logoColor=white)](https://github.com/WantedChip/studiobridge/actions)
[![Cloudflare Edge](https://img.shields.io/badge/Site-Deployed_on_Cloudflare-F38020?logo=cloudflare&logoColor=white)](https://github.com/WantedChip/studiobridge)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows_11_%2F_10_(x64_%26_ARM64)-0078D6?logo=windows&logoColor=white)](#system-requirements)
[![MCP](https://img.shields.io/badge/MCP-2026--07--28-purple?logo=anthropic&logoColor=white)](#ai-agent-setup)
[![Zero Kernel Drivers](https://img.shields.io/badge/Drivers-Zero_Kernel_Drivers-success.svg)](#why-studiobridge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[**Documentation**](docs/README.md) • [**Quickstart**](docs/quickstart.md) • [**Troubleshooting**](docs/troubleshooting.md) • [**Compatibility**](docs/compatibility.md) • [**Python SDK**](docs/api.md)

</div>

---

## ⚡ Why StudioBridge?

StudioBridge transforms FL Studio into an extensible, programmable audio environment for both human creators and autonomous AI assistants:

- 🤖 **Native AI Agent Integration:** Official Model Context Protocol (MCP) server for Claude Desktop, Cursor, Windsurf, Copilot, Cline, Codex, and Antigravity.
- 🛡️ **Zero Kernel Drivers:** No risky third-party kernel drivers or blue-screen hazards. Runs completely driverless on Windows 11 using native **Windows MIDI Services (WMS)** loopback and pure-Python `ctypes` WinMM.
- 🔒 **Safe, Verified & Reversible Writes:** Sessions default to read-only protection. Every write operation is verified with instant read-back comparison against target tolerances and recorded in an append-only mutation journal for one-click rollback.
- ⚡ **Sub-Millisecond 2-Way SysEx RPC:** Sub-millisecond latency (p50: 0.42 ms) with CRC-16 integrity checks, automatic chunking, and HMAC-SHA256 replay defense.
- 🎼 **Offline Binary FLP Engine:** Read, inspect, diff, and mutate `.flp` project files directly in pure Python without launching the DAW.
- 🚀 **Headless Render Supervision:** Automate stem and master exports with process monitoring, timeout enforcement, and automated acoustic validation (WAV format, RMS energy, and true peak levels).
- 💻 **Snapdragon X & x64 Native:** Universal pure-Python wheel (`py3-none-any`) engineered from the ground up to execute natively on both Windows on ARM64 and Windows x64.

---

## 🎛️ The Four Control Planes

StudioBridge provides a coherent architecture across all four FL Studio interaction modes:

```
  AI CODING ASSISTANTS & AUTOMATION SCRIPTS
  (Claude Desktop | Cursor | Windsurf | Copilot | Cline | Python SDK)
                                |
                                v  [MCP / JSON-RPC / HTTP REST]
  +-------------------------------------------------------------+
  |                   STUDIOBRIDGE CORE BROKER                  |
  |   Loopback (127.0.0.1) | Token Auth | Mutation Journal (MID)|
  +-------------------------------------------------------------+
         |                    |                |             |
         v Plane 1            v Plane 2        v Plane 3     v Plane 4
  +---------------+   +---------------+  +------------+  +-----------+
  | Live SysEx    |   | Win32 UI      |  | Headless   |  | Offline   |
  | 2-Way RPC     |   | Actuator      |  | Render     |  | FLP       |
  | (Mixer/State) |   | (Piano Roll)  |  | Supervisor |  | Engine    |
  +---------------+   +---------------+  +------------+  +-----------+
         |                    |                |             |
         +--------------------+----------------+-------------+
                              |
                              v
                      IMAGE-LINE FL STUDIO
```

1. **Plane 1 (Live SysEx RPC):** Bidirectional mixer control, volume faders, stereo panning, mute/solo, transport playback, and live parameter telemetry.
2. **Plane 2 (Win32 UI Actuator):** Focus-guarded Piano Roll generator script triggering with automatic cursor restoration and modal dialog detection.
3. **Plane 3 (Headless Render Supervisor):** Command-line batch export (`FL64.exe`) with child process isolation and audio signal validation.
4. **Plane 4 (Offline FLP Binary Engine):** AST-level project inspection, structural invariant checking, and lossless project mutations.

---

## 🚀 Quickstart in 3 Steps

### Step 1: Install StudioBridge

```bash
# Recommended: Install via uv
uv tool install studiobridge

# Alternative: Install via pip
pip install studiobridge
```

### Step 2: Configure Loopback & Install Script

```bash
# Set up native Windows MIDI loopback endpoints
sbridge setup loopback

# Install controller script into FL Studio hardware settings
sbridge setup install
```

In FL Studio, open **MIDI Settings** (<kbd>F10</kbd>), set `StudioBridge Out` to controller type **StudioBridge** on **Port 10**, and enable `StudioBridge In` on **Port 10**.

### Step 3: Run the Health Check

```bash
sbridge doctor
```

When all diagnostic checks pass green, your DAW is connected and ready!

---

## 🤖 AI Agent Setup

Add StudioBridge to your coding assistant in seconds:

### Claude Desktop
Add to `%APPDATA%\Claude\claude_desktop_config.json`:
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
Add to `.cursor/mcp.json`:
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
Add to `~/.codeium/windsurf/mcp_config.json`:
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
Add to `.vscode/mcp.json`:
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

*For Cline, Codex, Antigravity, Claude Code, Gemini CLI, and Zed configurations, see the [Full Quickstart Guide](docs/quickstart.md).*

---

## 🐍 Python SDK in Action

StudioBridge provides a fully-typed, elegant Python client:

```python
from studiobridge import Studio

# Connect to the local DAW session
with Studio.connect() as studio:
    # 1. Transport control
    if not studio.transport.is_playing():
        studio.transport.start()
        print(f"Transport started at {studio.transport.get_tempo()} BPM")

    # 2. Query and balance mixer tracks
    master_vol = studio.mixer.get_volume(0)
    print(f"Master volume: {master_vol:.2f}")

    # 3. Safe transactions with automatic rollback on error
    with studio.transaction():
        studio.mixer.set_volume(track=1, volume=0.8)
        studio.mixer.set_pan(track=1, pan=-0.25)

    # 4. Channel rack inspection
    for channel in studio.channels.get_channels():
        print(f"Channel [{channel.index}]: {channel.name}")
```

*Prefer async? Use `async with AsyncStudio.connect() as studio:` for native asyncio workflows.*

---

## 💻 Command Line Utilities

StudioBridge ships with a rich command-line tool (`sbridge`):

```bash
# Environment diagnostics and port validation
sbridge doctor

# Test bidirectional SysEx communication
sbridge hello

# Inspect an offline .flp project file
sbridge flp inspect my_song.flp

# Run local HTTP REST & Streamable HTTP server
sbridge serve --port 8080

# Direct command dispatch
sbridge call transport.isPlaying
sbridge call mixer.getTrackVolume --args '{"track": 0}'

# Inspect mutation journal records
sbridge journal list
```

---

## 📋 System Requirements

| Requirement | Specification |
| :--- | :--- |
| **Operating System** | Windows 11 (recommended) or Windows 10 64-bit |
| **Architecture** | Windows x64 or Windows on ARM64 (Qualcomm Snapdragon X) |
| **Python** | Python 3.10, 3.11, or 3.12 (pure Python, 64-bit) |
| **FL Studio** | FL Studio 21.2+ or FL Studio 24.1+ |
| **MIDI Subsystem** | Windows MIDI Services (WMS native) or loopMIDI |

---

## 📚 Documentation & Resources

- 📖 [**Documentation Hub**](docs/README.md) — Comprehensive architecture and usage guide
- 🚀 [**Quickstart Guide**](docs/quickstart.md) — 5-minute setup for all AI assistants
- 🩺 [**Troubleshooting & Doctor Checks**](docs/troubleshooting.md) — Diagnostic code directory (`D-ENV-01` to `D-SEC-01`)
- 📊 [**Compatibility Matrix**](docs/compatibility.md) — Hardware and FL Studio capability matrix
- 🐍 [**Python SDK Reference**](docs/api.md) — Complete Python API namespaces and examples
- 📜 [**Changelog**](CHANGELOG.md) — Detailed version history and release notes
- 🔒 [**Security Policy**](SECURITY.md) — Vulnerability reporting and defense-in-depth model

---

## 🤝 Contributing

We welcome contributions! Please check our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) for details on setting up your development environment and running tests.

---

## ⚖️ License & Trademark Notice

StudioBridge is licensed under the [MIT License](LICENSE).

*Disclaimer:* StudioBridge is an independent, clean-room open-source project. FL Studio is a registered trademark of Image-Line Software NV. StudioBridge is not affiliated with, endorsed by, or associated with Image-Line Software NV.
