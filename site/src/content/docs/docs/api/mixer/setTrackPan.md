---
title: "mixer.setTrackPan"
description: "Reference card for mixer.setTrackPan in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.setTrackPan`

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
