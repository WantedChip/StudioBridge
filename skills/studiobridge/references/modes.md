# Safety Modes and Confirmation Protocol

StudioBridge implements defense-in-depth safety controls across sessions and tool execution.

## 1. Safety Modes Overview

StudioBridge defines three primary operational safety modes:

```
[ read_only ] ──(challenge / user confirm)──> [ write ] ──(explicit opt-in)──> [ unsafe ]
```

### 1. `read_only` (Default Mode)
- **All mutating operations are blocked** before touching the wire or FL Studio host.
- Calling a mutating tool (`mixer_set`, `channel_set`, `transport_control`, etc.) raises a confirmation challenge.
- The server responds with `needs_confirmation: true`, a challenge message, and a cryptographically secure `confirm_token`.
- Inspection tools (`project_get`, `mixer_get`, `channels_get`, `patterns_get`, `transport_get`, `studio_status`) execute freely.

### 2. `write` (`write_autonomous` / `write_with_confirm`)
- Enables mutations to standard mixer tracks, channels, patterns, and transport.
- Requires all writes to follow the **Verified Write Loop** (`[VER-01..04]`): mutations are read back from host state and verified against declared numerical tolerances.
- **Protected targets** (Track 0, tempo changes, destructive file actions) are still gated and require explicit authorization.
- Mutations are recorded in the append-only mutation journal.

### 3. `unsafe`
- Bypasses readback verification and tolerance checks.
- Intended solely for high-frequency automation or bulk streaming where readback overhead is unacceptable.
- Must be explicitly requested by the user. Agents should **never** switch to `unsafe` autonomously.

## 2. Confirmation Challenge Protocol

When a mutating tool is invoked in `read_only` mode, the MCP server returns a structured confirmation challenge instead of an error:

```json
{
  "needs_confirmation": true,
  "challenge": "Operation 'mixer_set' will modify mixer track 3 volume from 0.80 to 0.70. Approve this modification?",
  "confirm_token": "a4f89d3c2e1b...",
  "operation": "mixer_set",
  "args": {
    "track": 3,
    "volume": 0.70
  },
  "expires_in_seconds": 300
}
```

### Protocol Flow:
1. **Agent receives challenge**: The agent detects `needs_confirmation: true`.
2. **User elicitation**: The agent presents the proposed change clearly to the user, citing the track or parameter name, current value, and new target value.
3. **Execution with Token**: When approved by the user, the agent re-executes the tool call passing the received `confirm_token`:
   ```json
   {
     "name": "mixer_set",
     "arguments": {
       "track": 3,
       "volume": 0.70,
       "confirm_token": "a4f89d3c2e1b..."
     }
   }
   ```
4. **Autonomous Mode Switch**: Supplying a valid `confirm_token` automatically switches the session safety mode to `write` for subsequent verified operations.

## 3. Protected Target Interlocks

To protect against irreversible user work loss, certain critical targets are strictly classified as **Protected Targets** (`[SAF-02]`):

1. **Master Mixer Track (Track 0)**:
   - Modifications to master volume, pan, stereo separation, routing, or master effects.
   - Accidental drops or boosts to Track 0 can damage monitor speakers or distort master mix headroom.
2. **Project Tempo Adjustments**:
   - Setting `transport.setTempo` alters project-wide timebase for all audio clips and automations.
3. **Destructive File Overwrites**:
   - Saving over existing `.flp` files.

### Overriding Protected Targets:
To modify a protected target, the agent must:
1. Set `allow_protected: true` in the tool call arguments.
2. If in `read_only` or `write` mode, a dedicated protected challenge is generated.
3. Provide the specific confirmation token granted for that protected operation.

```json
{
  "name": "mixer_set",
  "arguments": {
    "track": 0,
    "volume": 0.80,
    "allow_protected": true,
    "confirm_token": "prot_89bc21..."
  }
}
```

## 4. Switching Modes Explicitly

Agents can switch safety modes using `studio_set_mode`:

```json
{
  "name": "studio_set_mode",
  "arguments": {
    "mode": "write"
  }
}
```

- When switching to `write`, if previously in `read_only`, the user should be notified.
- When switching to `unsafe`, explicit user consent is required. If called without user authorization, the server prompts for confirmation.
