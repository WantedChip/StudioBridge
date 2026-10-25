---
title: "channels — Channel Rack & Generators"
description: "Complete API reference for the channels module (21 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `channels` module provides direct control over FL Studio's channel rack & generators.

- **Functions:** 21
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`channelCount`](#channelcount) | Read-only | `int` | v1 | Return the total count of generator and sampler channels. |
| [`channelNumber`](#channelnumber) | Read-only | `int` | v1 | Retrieve numeric index for channel. |
| [`getChannelColor`](#getchannelcolor) | Read-only | `int` | v1 | Retrieve display color code for channel. |
| [`getChannelName`](#getchannelname) | Read-only | `str` | v1 | Retrieve display name for channel. |
| [`getChannelPan`](#getchannelpan) | Read-only | `float` | v1 | Retrieve stereo pan value for channel. |
| [`getChannelPitch`](#getchannelpitch) | Read-only | `float` | v1 | Retrieve pitch offset value for channel. |
| [`getChannelVolume`](#getchannelvolume) | Read-only | `float` | v1 | Retrieve volume level for channel. |
| [`getTargetFxTrack`](#gettargetfxtrack) | Read-only | `int` | v1 | Retrieve target mixer insert track routed for channel. |
| [`incEventValue`](#inceventvalue) | **Mutating** | `None` | v1 | Increment or decrement channel event automation parameter. |
| [`isChannelMuted`](#ischannelmuted) | Read-only | `bool` | v1 | Query whether channel audio generation is muted. |
| [`isChannelSolo`](#ischannelsolo) | Read-only | `bool` | v1 | Query whether channel is soloed in channel rack. |
| [`muteChannel`](#mutechannel) | **Mutating** | `None` | v1 | Toggle or set mute state for channel. |
| [`selectChannel`](#selectchannel) | **Mutating** | `None` | v1 | Select or focus channel in channel rack. |
| [`selectedChannel`](#selectedchannel) | Read-only | `int` | v1 | Retrieve index of currently selected channel. |
| [`setChannelColor`](#setchannelcolor) | **Mutating** | `None` | v1 | Assign display color for channel. |
| [`setChannelName`](#setchannelname) | **Mutating** | `None` | v1 | Assign name label for channel. |
| [`setChannelPan`](#setchannelpan) | **Mutating** | `None` | v1 | Set stereo pan position for channel. |
| [`setChannelPitch`](#setchannelpitch) | **Mutating** | `None` | v1 | Set pitch tune offset for channel. |
| [`setChannelVolume`](#setchannelvolume) | **Mutating** | `None` | v1 | Set volume level for channel. |
| [`setTargetFxTrack`](#settargetfxtrack) | **Mutating** | `None` | v1 | Assign target mixer insert track for channel. |
| [`soloChannel`](#solochannel) | **Mutating** | `None` | v1 | Toggle or set solo state for channel. |

---

## Detailed Function Reference

### `channelCount`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/channelcount/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/channelCount`

Return the total count of generator and sampler channels.

#### Signature

```python
def channelCount(mode: int = 0) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | Yes | — | API v1 | — |

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

### `channelNumber`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/channelnumber/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/channelNumber`

Retrieve numeric index for channel.

#### Signature

```python
def channelNumber(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `getChannelColor`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/getchannelcolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/getChannelColor`

Retrieve display color code for channel.

#### Signature

```python
def getChannelColor(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `getChannelName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/getchannelname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/getChannelName`

Retrieve display name for channel.

#### Signature

```python
def getChannelName(index: int) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `getChannelPan`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/getchannelpan/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/getChannelPan`

Retrieve stereo pan value for channel.

#### Signature

```python
def getChannelPan(index: int) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `getChannelPitch`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/getchannelpitch/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/getChannelPitch`

Retrieve pitch offset value for channel.

#### Signature

```python
def getChannelPitch(index: int) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `getChannelVolume`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/getchannelvolume/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/getChannelVolume`

Retrieve volume level for channel.

#### Signature

```python
def getChannelVolume(index: int) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `getTargetFxTrack`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/gettargetfxtrack/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/getTargetFxTrack`

Retrieve target mixer insert track routed for channel.

#### Signature

```python
def getTargetFxTrack(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `incEventValue`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/inceventvalue/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/incEventValue`

Increment or decrement channel event automation parameter.

#### Signature

```python
def incEventValue(
    eventId: int,
    value: int,
    step: int = 0,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventId` | `int` | No | — | API v1 | — |
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

### `isChannelMuted`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/ischannelmuted/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/isChannelMuted`

Query whether channel audio generation is muted.

#### Signature

```python
def isChannelMuted(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `isChannelSolo`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/ischannelsolo/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/isChannelSolo`

Query whether channel is soloed in channel rack.

#### Signature

```python
def isChannelSolo(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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

### `muteChannel`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/mutechannel/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/muteChannel`

Toggle or set mute state for channel.

#### Signature

```python
def muteChannel(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
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

### `selectChannel`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/selectchannel/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/selectChannel`

Select or focus channel in channel rack.

#### Signature

```python
def selectChannel(index: int, value: int = 1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
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

### `selectedChannel`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/selectedchannel/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/selectedChannel`

Retrieve index of currently selected channel.

#### Signature

```python
def selectedChannel() -> int: ...
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

### `setChannelColor`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/setchannelcolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/setChannelColor`

Assign display color for channel.

#### Signature

```python
def setChannelColor(index: int, color: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
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

### `setChannelName`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/setchannelname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/setChannelName`

Assign name label for channel.

#### Signature

```python
def setChannelName(index: int, name: str) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getChannelName`, compare: `exact`, settle: `immediatems`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setChannelPan`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/setchannelpan/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/setChannelPan`

Set stereo pan position for channel.

#### Signature

```python
def setChannelPan(index: int, pan: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `pan` | `float` | No | `[-1, 1]` | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getChannelPan`, compare: `approx`, settle: `idle1ms`, tol: `0.005`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setChannelPitch`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/setchannelpitch/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/setChannelPitch`

Set pitch tune offset for channel.

#### Signature

```python
def setChannelPitch(index: int, pitch: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `pitch` | `float` | No | — | API v1 | — |

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

### `setChannelVolume`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/setchannelvolume/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/setChannelVolume`

Set volume level for channel.

#### Signature

```python
def setChannelVolume(index: int, volume: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `volume` | `float` | No | `[0, 1]` | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getChannelVolume`, compare: `approx`, settle: `idle1ms`, tol: `0.005`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setTargetFxTrack`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/settargetfxtrack/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/setTargetFxTrack`

Assign target mixer insert track for channel.

#### Signature

```python
def setTargetFxTrack(index: int, track: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `track` | `int` | No | `[0, 126]` | API v1 | — |

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

### `soloChannel`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/channels/solochannel/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/channels/soloChannel`

Toggle or set solo state for channel.

#### Signature

```python
def soloChannel(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
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

