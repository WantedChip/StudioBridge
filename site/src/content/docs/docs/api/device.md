---
title: "device — Hardware Controller & Device Surface"
description: "Complete API reference for the device module (9 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `device` module provides direct control over FL Studio's hardware controller & device surface.

- **Functions:** 9
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`baseTrackSelect`](#basetrackselect) | **Mutating** | `None` | v1 | Offset active track bank on hardware controller. |
| [`dispatch`](#dispatch) | **Mutating** | `None` | v1 | Dispatch internal hardware controller event message. |
| [`forwardMIDICC`](#forwardmidicc) | **Mutating** | `None` | v1 | Forward raw MIDI Continuous Controller message to host. |
| [`getName`](#getname) | Read-only | `str` | v1 | Retrieve configured controller script device name. |
| [`getPortNumber`](#getportnumber) | Read-only | `int` | v1 | Retrieve MIDI port index assigned to controller script. |
| [`isAssigned`](#isassigned) | Read-only | `bool` | v1 | Query whether controller script is linked to a valid port. |
| [`midiOutMsg`](#midioutmsg) | **Mutating** | `None` | v1 | Send short 3-byte MIDI message to hardware output port. |
| [`midiOutSysex`](#midioutsysex) | **Mutating** | `None` | v1 | Send raw SysEx byte sequence to hardware output port. |
| [`processMIDICC`](#processmidicc) | **Mutating** | `int` | v1 | Process incoming MIDI CC through active mapping table. |

---

## Detailed Function Reference

### `baseTrackSelect`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/basetrackselect/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/baseTrackSelect`

Offset active track bank on hardware controller.

#### Signature

```python
def baseTrackSelect(offset: int, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `offset` | `int` | No | — | API v1 | — |
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

### `dispatch`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/dispatch/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/dispatch`

Dispatch internal hardware controller event message.

#### Signature

```python
def dispatch(messageId: int, value: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `messageId` | `int` | No | — | API v1 | — |
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

### `forwardMIDICC`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/forwardmidicc/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/forwardMIDICC`

Forward raw MIDI Continuous Controller message to host.

#### Signature

```python
def forwardMIDICC(
    status: int,
    data1: int,
    data2: int,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `status` | `int` | No | — | API v1 | — |
| `data1` | `int` | No | — | API v1 | — |
| `data2` | `int` | No | — | API v1 | — |

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

### `getName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/getname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/getName`

Retrieve configured controller script device name.

#### Signature

```python
def getName() -> str: ...
```

#### Parameters

This function takes no parameters.

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

### `getPortNumber`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/getportnumber/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/getPortNumber`

Retrieve MIDI port index assigned to controller script.

#### Signature

```python
def getPortNumber() -> int: ...
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

### `isAssigned`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/isassigned/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/isAssigned`

Query whether controller script is linked to a valid port.

#### Signature

```python
def isAssigned() -> bool: ...
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

### `midiOutMsg`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/midioutmsg/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/midiOutMsg`

Send short 3-byte MIDI message to hardware output port.

#### Signature

```python
def midiOutMsg(message: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `message` | `int` | No | — | API v1 | — |

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

### `midiOutSysex`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/midioutsysex/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/midiOutSysex`

Send raw SysEx byte sequence to hardware output port.

#### Signature

```python
def midiOutSysex(data: bytes) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `data` | `bytes` | No | — | API v1 | — |

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

### `processMIDICC`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/device/processmidicc/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/device/processMIDICC`

Process incoming MIDI CC through active mapping table.

#### Signature

```python
def processMIDICC(event: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event` | `int` | No | — | API v1 | — |

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

