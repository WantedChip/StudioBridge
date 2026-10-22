# studiobridge

<!-- mcp-name: io.github.wantedchip/studiobridge -->

Zero-dependency npm launcher shim for [StudioBridge](https://github.com/WantedChip/studiobridge) — the AI agent and developer bridge to Image-Line FL Studio.

This package enables JavaScript-first workflows, coding agents (Claude Code, Cursor, Windsurf, Zed, etc.), and MCP clients to launch StudioBridge seamlessly without managing Python environments directly.

## Usage

Run the StudioBridge MCP server via `npx`:

```bash
# Launch MCP server for AI coding agents
npx -y studiobridge mcp

# Command-line interface inspection
npx -y studiobridge hello
npx -y studiobridge status
```

Or configure in your MCP client settings (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "npx",
      "args": ["-y", "studiobridge", "mcp"]
    }
  }
}
```

On native Windows environments, if your client does not resolve `.cmd` shims automatically:

```json
{
  "mcpServers": {
    "studiobridge": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "studiobridge", "mcp"]
    }
  }
}
```

## Runtime Resolution

The launcher checks for available execution backends in the following order:

1. **`SBRIDGE_PY_CMD`**: Custom Python executable or wrapper command specified in environment variables.
2. **`uvx`** (recommended): Runs the pinned `studiobridge` distribution via Astral `uv`.
3. **`pipx`**: Runs the pinned `studiobridge` distribution via `pipx run`.
4. **Python runtime**: Discovers a local Python 3.10+ runtime (`py`, `python`, `python3`), using pre-installed packages or managing a cached virtual environment.

## Stdio Discipline

To ensure strict compatibility with the Model Context Protocol (MCP) JSON-RPC stream, this launcher guarantees that `stdout` is never polluted with banner text, logs, or diagnostics. All diagnostic and error messages are written exclusively to `stderr`.

## License

MIT License. See [LICENSE](LICENSE) for details.
