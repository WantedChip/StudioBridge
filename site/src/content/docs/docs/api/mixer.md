---
title: "mixer — Mixer Tracks, Routing & Volume"
description: "Complete API reference for the mixer module (23 functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The `mixer` module provides direct control over FL Studio's mixer tracks, routing & volume.

- **Functions:** 23
- **Execution Plane:** `midi` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

| Function | Type | Return | Since | Summary |
| :--- | :--- | :--- | :--- | :--- |
| [`armTrack`](#armtrack) | **Mutating** | `None` | v1 | Toggle or set recording arm status for mixer track. |
| [`enableTrack`](#enabletrack) | **Mutating** | `None` | v1 | Enable or disable audio processing for mixer track. |
| [`enableTrackSlots`](#enabletrackslots) | **Mutating** | `None` | v1 | Enable or disable effect slots on mixer track. |
| [`getSongStepPos`](#getsongsteppos) | Read-only | `int` | v1 | Retrieve current step position along the mixer timeline. |
| [`getTrackColor`](#gettrackcolor) | Read-only | `int` | v1 | Retrieve RGB color code for mixer track. |
| [`getTrackName`](#gettrackname) | Read-only | `str` | v1 | Retrieve display name for mixer track. |
| [`getTrackNumber`](#gettracknumber) | Read-only | `int` | v1 | Retrieve numeric index for mixer track. |
| [`getTrackPan`](#gettrackpan) | Read-only | `float` | v1 | Retrieve stereo panorama position for mixer track. |
| [`getTrackSlotsEnabled`](#gettrackslotsenabled) | Read-only | `bool` | v1 | Query whether effect slots are enabled on mixer track. |
| [`getTrackVolume`](#gettrackvolume) | Read-only | `float` | v1 | Retrieve volume level for mixer track. |
| [`isTrackArmed`](#istrackarmed) | Read-only | `bool` | v1 | Query whether mixer track is armed for disk recording. |
| [`isTrackEnabled`](#istrackenabled) | Read-only | `bool` | v1 | Query whether mixer track is active and processing audio. |
| [`isTrackMuted`](#istrackmuted) | Read-only | `bool` | v1 | Query whether mixer track output is muted. |
| [`isTrackSolo`](#istracksolo) | Read-only | `bool` | v1 | Query whether mixer track is soloed. |
| [`linkTrackToChannel`](#linktracktochannel) | **Mutating** | `None` | v1 | Route active channel directly to selected mixer track. |
| [`muteTrack`](#mutetrack) | **Mutating** | `None` | v1 | Toggle or set mute state for mixer track. |
| [`setTrackColor`](#settrackcolor) | **Mutating** | `None` | v1 | Assign display color for mixer track. |
| [`setTrackName`](#settrackname) | **Mutating** | `None` | v1 | Assign descriptive label for mixer track. |
| [`setTrackNumber`](#settracknumber) | **Mutating** | `None` | v1 | Assign track index routing for mixer track. |
| [`setTrackPan`](#settrackpan) | **Mutating** | `None` | v1 | Set stereo pan position for mixer track. |
| [`setTrackVolume`](#settrackvolume) | **Mutating** | `None` | v1 | Set output volume level for mixer track. |
| [`soloTrack`](#solotrack) | **Mutating** | `None` | v1 | Toggle or set solo state for mixer track. |
| [`trackCount`](#trackcount) | Read-only | `int` | v1 | Return the total number of available mixer tracks. |

---

## Detailed Function Reference

### `armTrack`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/armtrack/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/armTrack`

Toggle or set recording arm status for mixer track.

#### Signature

```python
def armTrack(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
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

### `enableTrack`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/enabletrack/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/enableTrack`

Enable or disable audio processing for mixer track.

#### Signature

```python
def enableTrack(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
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

### `enableTrackSlots`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/enabletrackslots/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/enableTrackSlots`

Enable or disable effect slots on mixer track.

#### Signature

```python
def enableTrackSlots(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
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

### `getSongStepPos`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/getsongsteppos/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getSongStepPos`

Retrieve current step position along the mixer timeline.

#### Signature

```python
def getSongStepPos() -> int: ...
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

### `getTrackColor`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/gettrackcolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getTrackColor`

Retrieve RGB color code for mixer track.

#### Signature

```python
def getTrackColor(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `getTrackName`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/gettrackname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getTrackName`

Retrieve display name for mixer track.

#### Signature

```python
def getTrackName(index: int) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `getTrackNumber`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/gettracknumber/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getTrackNumber`

Retrieve numeric index for mixer track.

#### Signature

```python
def getTrackNumber(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `getTrackPan`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/gettrackpan/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getTrackPan`

Retrieve stereo panorama position for mixer track.

#### Signature

```python
def getTrackPan(index: int) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `getTrackSlotsEnabled`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/gettrackslotsenabled/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getTrackSlotsEnabled`

Query whether effect slots are enabled on mixer track.

#### Signature

```python
def getTrackSlotsEnabled(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `getTrackVolume`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/gettrackvolume/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/getTrackVolume`

Retrieve volume level for mixer track.

#### Signature

```python
def getTrackVolume(index: int) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `isTrackArmed`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/istrackarmed/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/isTrackArmed`

Query whether mixer track is armed for disk recording.

#### Signature

```python
def isTrackArmed(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `isTrackEnabled`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/istrackenabled/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/isTrackEnabled`

Query whether mixer track is active and processing audio.

#### Signature

```python
def isTrackEnabled(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `isTrackMuted`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/istrackmuted/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/isTrackMuted`

Query whether mixer track output is muted.

#### Signature

```python
def isTrackMuted(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `isTrackSolo`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/istracksolo/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/isTrackSolo`

Query whether mixer track is soloed.

#### Signature

```python
def isTrackSolo(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

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

### `linkTrackToChannel`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/linktracktochannel/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/linkTrackToChannel`

Route active channel directly to selected mixer track.

#### Signature

```python
def linkTrackToChannel(mode: int) -> None: ...
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

### `muteTrack`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/mutetrack/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/muteTrack`

Toggle or set mute state for mixer track.

#### Signature

```python
def muteTrack(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `isTrackMuted`, compare: `exact`, settle: `immediatems`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setTrackColor`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/settrackcolor/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/setTrackColor`

Assign display color for mixer track.

#### Signature

```python
def setTrackColor(index: int, color: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
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

### `setTrackName`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/settrackname/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/setTrackName`

Assign descriptive label for mixer track.

#### Signature

```python
def setTrackName(index: int, name: str) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getTrackName`, compare: `exact`, settle: `immediatems`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setTrackNumber`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/settracknumber/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/setTrackNumber`

Assign track index routing for mixer track.

#### Signature

```python
def setTrackNumber(index: int, number: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `number` | `int` | No | — | API v1 | — |

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

### `setTrackPan`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/settrackpan/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/setTrackPan`

Set stereo pan position for mixer track.

#### Signature

```python
def setTrackPan(index: int, pan: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `pan` | `float` | No | `[-1, 1]` | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getTrackPan`, compare: `approx`, settle: `idle1ms`, tol: `0.005`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `setTrackVolume`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/settrackvolume/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/setTrackVolume`

Set output volume level for mixer track.

#### Signature

```python
def setTrackVolume(
    index: int,
    volume: float,
    pickupMode: int = 0,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `volume` | `float` | No | `[0, 1]` | API v1 | — |
| `pickupMode` | `int` | Yes | — | API v16 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getTrackVolume`, compare: `approx`, settle: `idle1ms`, tol: `0.005`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |

---

### `soloTrack`

<div class="api-card-header">
  <span class="api-badge badge-mutating">MUTATING</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/solotrack/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/soloTrack`

Toggle or set solo state for mixer track.

#### Signature

```python
def soloTrack(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
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

### `trackCount`

<div class="api-card-header">
  <span class="api-badge badge-readonly">READ-ONLY</span>
  <span class="api-badge badge-plane">midi</span>
  <a href="/docs/api/mixer/trackcount/" class="api-permalink">Permalink</a>
</div>

**Resource URI:** `studio://api/mixer/trackCount`

Return the total number of available mixer tracks.

#### Signature

```python
def trackCount() -> int: ...
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

