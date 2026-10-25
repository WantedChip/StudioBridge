---
title: "plugins — Plugin Parameters & VST/AU"
description: "Complete API reference for the plugins module (12 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `plugins` module provides direct control over FL Studio's plugin parameters & vst/au.

- **Functions:** 12
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`getColor`](#getcolor) | Read-only | `int` | v1 | Retrieve color code for plugin instance. |
| [`getColorName`](#getcolorname) | Read-only | `str` | v1 | Retrieve color name string for plugin instance. |
| [`getName`](#getname) | Read-only | `str` | v1 | Retrieve display name of loaded plugin. |
| [`getParamCount`](#getparamcount) | Read-only | `int` | v1 | Retrieve total count of automatable parameters in plugin. |
| [`getParamName`](#getparamname) | Read-only | `str` | v1 | Retrieve name of automatable parameter. |
| [`getParamValue`](#getparamvalue) | Read-only | `float` | v1 | Retrieve normalized value (0.0-1.0) of automatable parameter. |
| [`getPluginName`](#getpluginname) | Read-only | `str` | v1 | Retrieve generator or effect type identifier. |
| [`getPresetCount`](#getpresetcount) | Read-only | `int` | v1 | Retrieve total count of factory and user presets. |
| [`getPresetName`](#getpresetname) | Read-only | `str` | v1 | Retrieve preset title for given preset index. |
| [`isValid`](#isvalid) | Read-only | `bool` | v1 | Query whether plugin slot contains a valid, loaded plugin. |
| [`setParamValue`](#setparamvalue) | **Mutating** | `None` | v1 | Assign normalized automation value for plugin parameter. |
| [`showEditor`](#showeditor) | **Mutating** | `None` | v1 | Toggle display of graphical user interface editor for plugin. |

---

## Detailed Function Reference

### `getColor`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getcolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getColor`

Retrieve color code for plugin instance.

#### Signature

```python
def getColor(index: int, slot: int = -1) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getColorName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getcolorname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getColorName`

Retrieve color name string for plugin instance.

#### Signature

```python
def getColorName(index: int, slot: int = -1) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getName`

Retrieve display name of loaded plugin.

#### Signature

```python
def getName(index: int, slot: int = -1) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getParamCount`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getparamcount/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getParamCount`

Retrieve total count of automatable parameters in plugin.

#### Signature

```python
def getParamCount(index: int, slot: int = -1) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getParamName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getparamname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getParamName`

Retrieve name of automatable parameter.

#### Signature

```python
def getParamName(
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getParamValue`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getparamvalue/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getParamValue`

Retrieve normalized value (0.0-1.0) of automatable parameter.

#### Signature

```python
def getParamValue(
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getPluginName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getpluginname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getPluginName`

Retrieve generator or effect type identifier.

#### Signature

```python
def getPluginName(index: int, slot: int = -1) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getPresetCount`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getpresetcount/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getPresetCount`

Retrieve total count of factory and user presets.

#### Signature

```python
def getPresetCount(index: int, slot: int = -1) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `getPresetName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/getpresetname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/getPresetName`

Retrieve preset title for given preset index.

#### Signature

```python
def getPresetName(
    presetIndex: int,
    index: int,
    slot: int = -1,
) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `presetIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `isValid`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/isvalid/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/isValid`

Query whether plugin slot contains a valid, loaded plugin.

#### Signature

```python
def isValid(index: int, slot: int = -1) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `setParamValue`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/setparamvalue/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/setParamValue`

Assign normalized automation value for plugin parameter.

#### Signature

```python
def setParamValue(
    value: float,
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `float` | No | `[0, 1]` | API v1 | — |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

### `showEditor`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/plugins/showeditor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/plugins/showEditor`

Toggle display of graphical user interface editor for plugin.

#### Signature

```python
def showEditor(index: int, slot: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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

