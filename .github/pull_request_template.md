## Description

<!-- Describe your changes in detail -->

## Related Issue

<!-- Closes #123 / Relates to #123 -->

## Control Plane Affected

- [ ] Plane 1: Live MIDI SysEx RPC (Mixer, Transport, Channels, Parameters)
- [ ] Plane 2: Win32 UI Actuator (Piano roll scripts, Focus guards)
- [ ] Plane 3: Headless Render Supervisor (Audio export, CLI)
- [ ] Plane 4: Offline FLP Binary Engine (Project parser, Mutator)
- [ ] Interfaces: Model Context Protocol (MCP) / CLI / HTTP REST
- [ ] Documentation / Website / Packaging

## Quality Checklist

- [ ] My code adheres to the project's coding standards and style guidelines.
- [ ] I have verified that zero native/compiled C dependencies are introduced (`Rule 1`).
- [ ] I have kept public APIs strictly typed (`pyright`).
- [ ] I have run tests and added unit tests for new behavior (`pytest`).
- [ ] I have verified brand token integrity (`python tools/rename.py --check`).
- [ ] I have ensured zero internal planning artifacts or spec references leak into public files (`Rule 11`).
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat`, `fix`, `docs`, `test`, `refactor`).

## Verification Output

```bash
# Paste verification check results below:
uv run ruff check .
uv run pyright
uv run pytest
```
