# Progressive API Discovery and Manifest Documentation

FL Studio's Python scripting API contains hundreds of functions across 10 official modules. Function names, parameter conventions, return types, and version availability vary significantly across FL Studio releases.

To prevent hallucinations and API misuse, agents **MUST** use progressive discovery (`api_search` and `api_describe`).

## 1. The 10 FL Studio Scripting Modules

| Module | Core Responsibilities | Typical Operations |
|---|---|---|
| `mixer` | Mixer tracks, faders, panning, mute/solo, routing, peaks | `getTrackVolume`, `setTrackVolume`, `getTrackPan`, `isTrackMuted` |
| `channels` | Channel rack instruments, samplers, volume, pan | `channelCount`, `getChannelName`, `setChannelVolume`, `getGridBit` |
| `patterns` | Pattern creation, active selection, pattern length | `patternCount`, `patternNumber`, `getPatternName`, `setPatternName` |
| `transport` | Playback, stop, record, song position, master tempo | `isPlaying`, `start`, `stop`, `record`, `getSongPos`, `getSongLength` |
| `playlist` | Playlist tracks, live performance blocks, clip placement | `trackCount`, `getTrackName`, `muteTrack`, `lockTrack` |
| `plugins` | VST/AU and native plugin parameter querying and tweaking | `isValidIndex`, `getParamName`, `getParamValue`, `setParamValue` |
| `general` | Undo/redo stack, project properties, dialog management | `undo`, `undoUp`, `saveUndo`, `getVersion`, `restoreWindows` |
| `ui` | Window focus, channel rack visibility, piano roll view | `showWindow`, `getVisible`, `setFocused`, `crDisplayRect` |
| `device` | MIDI hardware routing, port IDs, dispatching events | `dispatch`, `findEventName`, `portNumber` |
| `arrangement`| Arrangement layout indexing and selection | `getArrangementCount`, `getArrangementName` |

## 2. Searching the API: `api_search`

Before writing code or invoking raw commands, search the manifest:

```json
{
  "name": "api_search",
  "arguments": {
    "query": "volume",
    "module": "mixer",
    "limit": 10
  }
}
```

### Response Example:
```json
{
  "total": 3,
  "results": [
    {
      "module": "mixer",
      "name": "getTrackVolume",
      "signature": "getTrackVolume(index: int) -> float",
      "summary": "Returns the volume fader level for the specified mixer track (0.0 to 1.0)."
    },
    {
      "module": "mixer",
      "name": "setTrackVolume",
      "signature": "setTrackVolume(index: int, value: float) -> None",
      "summary": "Sets the volume fader level for the specified mixer track (0.0 to 1.0)."
    }
  ]
}
```

## 3. Deep Function Inspection: `api_describe`

To inspect full parameter types, since-version, quirks, and card examples:

```json
{
  "name": "api_describe",
  "arguments": {
    "function": "mixer.setTrackVolume"
  }
}
```

### Information Provided in Manifest Cards:
1. **Signature & Types**: Exact Python parameter types and return annotations.
2. **Since Version**: The minimum FL Studio version supporting this call (e.g. `20.7`, `21.0`).
3. **Quirks & Bugs**: Known host idiosyncrasies (e.g. quantization, required UI focus, non-blocking delays).
4. **Tolerance**: The declared numeric tolerance for verification (`0.01`).
5. **Usage Example**: Minimal, correct Python code snippet.

## 4. MCP URI Resources

The API documentation is also accessible as standard MCP resources:
- Catalog of a module: `studio://api/mixer`
- Specific function documentation card: `studio://api/mixer/setTrackVolume`

Agents can read these resources directly to include full function cards in context.
