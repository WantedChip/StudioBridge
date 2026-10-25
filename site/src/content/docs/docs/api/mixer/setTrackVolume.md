---
title: "mixer.setTrackVolume"
description: "Reference card for mixer.setTrackVolume in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.setTrackVolume`

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
