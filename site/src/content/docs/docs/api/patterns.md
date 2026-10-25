---
title: "patterns — Patterns, Clips & Sequencer"
description: "Complete API reference for the patterns module (12 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `patterns` module provides direct control over FL Studio's patterns, clips & sequencer.

- **Functions:** 12
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`ensureValidPattern`](#ensurevalidpattern) | **Mutating** | `None` | v1 | Ensure pattern exists and is initialized. |
| [`getPatternColor`](#getpatterncolor) | Read-only | `int` | v1 | Retrieve RGB color code for pattern. |
| [`getPatternLength`](#getpatternlength) | Read-only | `int` | v1 | Retrieve total length in steps for pattern. |
| [`getPatternName`](#getpatternname) | Read-only | `str` | v1 | Retrieve title name for pattern. |
| [`isPatternSelected`](#ispatternselected) | Read-only | `bool` | v1 | Query whether pattern is selected in picker. |
| [`jumpToPattern`](#jumptopattern) | **Mutating** | `None` | v1 | Set active pattern and navigate to it in picker. |
| [`patternCount`](#patterncount) | Read-only | `int` | v1 | Return the total count of active patterns. |
| [`patternNumber`](#patternnumber) | Read-only | `int` | v1 | Retrieve current active pattern index. |
| [`selectPattern`](#selectpattern) | **Mutating** | `None` | v1 | Select pattern in playlist and picker. |
| [`setPatternColor`](#setpatterncolor) | **Mutating** | `None` | v1 | Assign display color for pattern. |
| [`setPatternLength`](#setpatternlength) | **Mutating** | `None` | v1 | Set total length in steps for pattern. |
| [`setPatternName`](#setpatternname) | **Mutating** | `None` | v1 | Assign name label for pattern. |

---

## Detailed Function Reference

### `ensureValidPattern`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/ensurevalidpattern/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/ensureValidPattern`

Ensure pattern exists and is initialized.

#### Signature

```python
def ensureValidPattern(index: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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

### `getPatternColor`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/getpatterncolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/getPatternColor`

Retrieve RGB color code for pattern.

#### Signature

```python
def getPatternColor(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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

### `getPatternLength`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/getpatternlength/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/getPatternLength`

Retrieve total length in steps for pattern.

#### Signature

```python
def getPatternLength(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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

### `getPatternName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/getpatternname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/getPatternName`

Retrieve title name for pattern.

#### Signature

```python
def getPatternName(index: int) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

#### Return Value

- **Type:** `str`

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

### `isPatternSelected`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/ispatternselected/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/isPatternSelected`

Query whether pattern is selected in picker.

#### Signature

```python
def isPatternSelected(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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

### `jumpToPattern`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/jumptopattern/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/jumpToPattern`

Set active pattern and navigate to it in picker.

#### Signature

```python
def jumpToPattern(index: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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

### `patternCount`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/patterncount/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/patternCount`

Return the total count of active patterns.

#### Signature

```python
def patternCount() -> int: ...
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

### `patternNumber`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/patternnumber/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/patternNumber`

Retrieve current active pattern index.

#### Signature

```python
def patternNumber() -> int: ...
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

### `selectPattern`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/selectpattern/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/selectPattern`

Select pattern in playlist and picker.

#### Signature

```python
def selectPattern(index: int, value: int = 1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

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

### `setPatternColor`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/setpatterncolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/setPatternColor`

Assign display color for pattern.

#### Signature

```python
def setPatternColor(index: int, color: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `color` | `int` | No | — | API v1 | — |

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

### `setPatternLength`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/setpatternlength/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/setPatternLength`

Set total length in steps for pattern.

#### Signature

```python
def setPatternLength(index: int, length: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `length` | `int` | No | — | API v1 | — |

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

### `setPatternName`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/patterns/setpatternname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/patterns/setPatternName`

Assign name label for pattern.

#### Signature

```python
def setPatternName(index: int, name: str) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getPatternName`, compare: `exact`, settle: `immediatems`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

