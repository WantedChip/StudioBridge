---
title: "transport — Transport, Playback & Recording"
description: "Complete API reference for the transport module (17 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `transport` module provides direct control over FL Studio's transport, playback & recording.

- **Functions:** 17
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`continuousMove`](#continuousmove) | **Mutating** | `None` | v1 | Move the song playback position continuously. |
| [`fastForward`](#fastforward) | **Mutating** | `None` | v1 | Engage fast forward transport motion. |
| [`getLoopMode`](#getloopmode) | Read-only | `int` | v1 | Retrieve current loop playback mode. |
| [`getPlaybackSpeed`](#getplaybackspeed) | Read-only | `float` | v1 | Retrieve current playback speed multiplier. |
| [`getSongLength`](#getsonglength) | Read-only | `float` | v1 | Retrieve total song length in beats or seconds. |
| [`getSongPos`](#getsongpos) | Read-only | `float` | v1 | Retrieve normalized song position. |
| [`globalTransport`](#globaltransport) | **Mutating** | `int` | v1 | Dispatch a global transport action code. |
| [`isPlaying`](#isplaying) | Read-only | `bool` | v1 | Query whether transport playback is active. |
| [`isRecording`](#isrecording) | Read-only | `bool` | v1 | Query whether transport recording mode is active. |
| [`markerJump`](#markerjump) | **Mutating** | `None` | v1 | Jump playback to the previous or next timeline marker. |
| [`record`](#record) | **Mutating** | `None` | v1 | Toggle or arm recording state. |
| [`rewind`](#rewind) | **Mutating** | `None` | v1 | Engage rewind transport motion. |
| [`setLoopMode`](#setloopmode) | **Mutating** | `None` | v1 | Toggle loop playback mode. |
| [`setPlaybackSpeed`](#setplaybackspeed) | **Mutating** | `None` | v1 | Set transport playback speed factor. |
| [`setSongPos`](#setsongpos) | **Mutating** | `None` | v1 | Set the normalized playback cursor position. |
| [`start`](#start) | **Mutating** | `None` | v1 | Start transport playback. |
| [`stop`](#stop) | **Mutating** | `None` | v1 | Stop transport playback. |

---

## Detailed Function Reference

### `continuousMove`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/continuousmove/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/continuousMove`

Move the song playback position continuously.

#### Signature

```python
def continuousMove(value: int, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `int` | No | — | API v1 | — |
| `step` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `fastForward`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/fastforward/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/fastForward`

Engage fast forward transport motion.

#### Signature

```python
def fastForward(value: int = 2, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `int` | Yes | — | API v1 | — |
| `step` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `getLoopMode`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/getloopmode/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/getLoopMode`

Retrieve current loop playback mode.

#### Signature

```python
def getLoopMode() -> int: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `int`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `getPlaybackSpeed`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/getplaybackspeed/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/getPlaybackSpeed`

Retrieve current playback speed multiplier.

#### Signature

```python
def getPlaybackSpeed() -> float: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `float`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `getSongLength`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/getsonglength/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/getSongLength`

Retrieve total song length in beats or seconds.

#### Signature

```python
def getSongLength(mode: int = 0) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `float`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `getSongPos`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/getsongpos/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/getSongPos`

Retrieve normalized song position.

#### Signature

```python
def getSongPos(mode: int = 0) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `float`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `globalTransport`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/globaltransport/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/globalTransport`

Dispatch a global transport action code.

#### Signature

```python
def globalTransport(command: int, value: int = 0) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `command` | `int` | No | — | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `int`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `isPlaying`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/isplaying/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/isPlaying`

Query whether transport playback is active.

#### Signature

```python
def isPlaying() -> bool: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `bool`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `isRecording`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/isrecording/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/isRecording`

Query whether transport recording mode is active.

#### Signature

```python
def isRecording() -> bool: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `bool`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `markerJump`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/markerjump/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/markerJump`

Jump playback to the previous or next timeline marker.

#### Signature

```python
def markerJump(step: int, select: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `step` | `int` | No | — | API v1 | — |
| `select` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `record`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/record/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/record`

Toggle or arm recording state.

#### Signature

```python
def record() -> None: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `rewind`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/rewind/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/rewind`

Engage rewind transport motion.

#### Signature

```python
def rewind(value: int = 2, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `int` | Yes | — | API v1 | — |
| `step` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setLoopMode`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/setloopmode/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/setLoopMode`

Toggle loop playback mode.

#### Signature

```python
def setLoopMode() -> None: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setPlaybackSpeed`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/setplaybackspeed/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/setPlaybackSpeed`

Set transport playback speed factor.

#### Signature

```python
def setPlaybackSpeed(speed: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `speed` | `float` | No | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setSongPos`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/setsongpos/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/setSongPos`

Set the normalized playback cursor position.

#### Signature

```python
def setSongPos(pos: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pos` | `float` | No | `[0, 1]` | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getSongPos`, compare: `approx`, settle: `idle1ms`, tol: `0.01`, args: `[]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `start`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/start/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/start`

Start transport playback.

#### Signature

```python
def start() -> None: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `stop`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/transport/stop/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/transport/stop`

Stop transport playback.

#### Signature

```python
def stop() -> None: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |

