---
title: "general — General FL Studio DAW Engine"
description: "Complete API reference for the general module (10 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `general` module provides direct control over FL Studio's general fl studio daw engine.

- **Functions:** 10
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`clearChangedFlag`](#clearchangedflag) | **Mutating** | `None` | v1 | Reset project modified dirty flag. |
| [`getChangedFlag`](#getchangedflag) | Read-only | `int` | v1 | Retrieve project modified dirty bitmask. |
| [`getRecPPQ`](#getrecppq) | Read-only | `int` | v1 | Retrieve pulses-per-quarter-note resolution. |
| [`getVersion`](#getversion) | Read-only | `int` | v1 | Retrieve the host FL Studio API version integer. |
| [`processRECEvent`](#processrecevent) | **Mutating** | `int` | v1 | Dispatch automation recording event. |
| [`redo`](#redo) | **Mutating** | `None` | v1 | Redo the last undone edit in history. |
| [`restore`](#restore) | **Mutating** | `None` | v1 | Restore project to last clean save state. |
| [`saveUndo`](#saveundo) | **Mutating** | `None` | v1 | Push a labeled transaction checkpoint into undo history. |
| [`undo`](#undo) | **Mutating** | `None` | v1 | Undo the last edit action in history. |
| [`undoUp`](#undoup) | **Mutating** | `None` | v1 | Step upward through undo history stack. |

---

## Detailed Function Reference

### `clearChangedFlag`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/clearchangedflag/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/clearChangedFlag`

Reset project modified dirty flag.

#### Signature

```python
def clearChangedFlag() -> None: ...
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

### `getChangedFlag`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/getchangedflag/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/getChangedFlag`

Retrieve project modified dirty bitmask.

#### Signature

```python
def getChangedFlag() -> int: ...
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

### `getRecPPQ`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/getrecppq/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/getRecPPQ`

Retrieve pulses-per-quarter-note resolution.

#### Signature

```python
def getRecPPQ() -> int: ...
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

### `getVersion`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/getversion/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/getVersion`

Retrieve the host FL Studio API version integer.

#### Signature

```python
def getVersion() -> int: ...
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

### `processRECEvent`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/processrecevent/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/processRECEvent`

Dispatch automation recording event.

#### Signature

```python
def processRECEvent(
    eventId: int,
    value: int,
    flags: int = 0,
) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventId` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `flags` | `int` | Yes | — | API v1 | — |

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

### `redo`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/redo/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/redo`

Redo the last undone edit in history.

#### Signature

```python
def redo() -> None: ...
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

### `restore`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/restore/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/restore`

Restore project to last clean save state.

#### Signature

```python
def restore() -> None: ...
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

### `saveUndo`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/saveundo/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/saveUndo`

Push a labeled transaction checkpoint into undo history.

#### Signature

```python
def saveUndo(name: str, flags: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `name` | `str` | No | — | API v1 | — |
| `flags` | `int` | Yes | — | API v1 | — |

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

### `undo`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/undo/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/undo`

Undo the last edit action in history.

#### Signature

```python
def undo() -> None: ...
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

### `undoUp`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/general/undoup/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/general/undoUp`

Step upward through undo history stack.

#### Signature

```python
def undoUp() -> None: ...
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

