---
title: "ui — User Interface Windows & Focus"
description: "Complete API reference for the ui module (15 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `ui` module provides direct control over FL Studio's user interface windows & focus.

- **Functions:** 15
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`crDisplay`](#crdisplay) | **Mutating** | `None` | v1 | Update channel rack display control. |
| [`getFocused`](#getfocused) | Read-only | `bool` | v1 | Query whether specified FL Studio window currently holds focus. |
| [`getStepEditMode`](#getstepeditmode) | Read-only | `int` | v1 | Retrieve channel rack step sequencer edit mode. |
| [`getVersion`](#getversion) | Read-only | `int` | v1 | Retrieve UI subsystem API version. |
| [`getVisible`](#getvisible) | Read-only | `bool` | v1 | Query whether specified FL Studio window is currently visible. |
| [`getVisibleForm`](#getvisibleform) | Read-only | `bool` | v1 | Query whether floating tool form is currently visible. |
| [`hideWindow`](#hidewindow) | **Mutating** | `None` | v1 | Hide the designated FL Studio workspace window. |
| [`jog`](#jog) | **Mutating** | `None` | v1 | Send jog wheel navigation delta. |
| [`scrollWindow`](#scrollwindow) | **Mutating** | `None` | v1 | Scroll contents of specified window by delta. |
| [`setFocused`](#setfocused) | **Mutating** | `None` | v1 | Direct focus to the specified workspace window. |
| [`setFocusedForm`](#setfocusedform) | **Mutating** | `None` | v1 | Direct focus to floating form. |
| [`setStepEditMode`](#setstepeditmode) | **Mutating** | `None` | v1 | Configure channel rack step editing mode. |
| [`showWindow`](#showwindow) | **Mutating** | `None` | v1 | Display and bring forward the designated workspace window. |
| [`snapMode`](#snapmode) | Read-only | `int` | v1 | Retrieve current timeline snap grid setting. |
| [`snapWindow`](#snapwindow) | **Mutating** | `None` | v1 | Snap window position to preset desktop docking grid. |

---

## Detailed Function Reference

### `crDisplay`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/crdisplay/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/crDisplay`

Update channel rack display control.

#### Signature

```python
def crDisplay(
    index: int,
    value: int,
    mode: int = 0,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `mode` | `int` | Yes | — | API v1 | — |

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

### `getFocused`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/getfocused/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/getFocused`

Query whether specified FL Studio window currently holds focus.

#### Signature

```python
def getFocused(window: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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

### `getStepEditMode`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/getstepeditmode/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/getStepEditMode`

Retrieve channel rack step sequencer edit mode.

#### Signature

```python
def getStepEditMode() -> int: ...
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
  <a href="/docs/api/ui/getversion/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/getVersion`

Retrieve UI subsystem API version.

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

### `getVisible`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/getvisible/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/getVisible`

Query whether specified FL Studio window is currently visible.

#### Signature

```python
def getVisible(window: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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

### `getVisibleForm`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/getvisibleform/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/getVisibleForm`

Query whether floating tool form is currently visible.

#### Signature

```python
def getVisibleForm(formId: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `formId` | `int` | No | — | API v1 | — |

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

### `hideWindow`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/hidewindow/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/hideWindow`

Hide the designated FL Studio workspace window.

#### Signature

```python
def hideWindow(window: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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

### `jog`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/jog/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/jog`

Send jog wheel navigation delta.

#### Signature

```python
def jog(value: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `int` | No | — | API v1 | — |

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

### `scrollWindow`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/scrollwindow/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/scrollWindow`

Scroll contents of specified window by delta.

#### Signature

```python
def scrollWindow(window: int, delta: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |
| `delta` | `int` | No | — | API v1 | — |

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

### `setFocused`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/setfocused/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/setFocused`

Direct focus to the specified workspace window.

#### Signature

```python
def setFocused(window: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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

### `setFocusedForm`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/setfocusedform/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/setFocusedForm`

Direct focus to floating form.

#### Signature

```python
def setFocusedForm(formId: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `formId` | `int` | No | — | API v1 | — |

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

### `setStepEditMode`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/setstepeditmode/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/setStepEditMode`

Configure channel rack step editing mode.

#### Signature

```python
def setStepEditMode(mode: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | No | — | API v1 | — |

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

### `showWindow`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/showwindow/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/showWindow`

Display and bring forward the designated workspace window.

#### Signature

```python
def showWindow(window: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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

### `snapMode`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/snapmode/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/snapMode`

Retrieve current timeline snap grid setting.

#### Signature

```python
def snapMode() -> int: ...
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

### `snapWindow`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/ui/snapwindow/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/ui/snapWindow`

Snap window position to preset desktop docking grid.

#### Signature

```python
def snapWindow(window: int, mode: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |
| `mode` | `int` | No | — | API v1 | — |

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

