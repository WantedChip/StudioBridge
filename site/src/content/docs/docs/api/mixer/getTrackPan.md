---
title: "mixer.getTrackPan"
description: "Reference card for mixer.getTrackPan in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.getTrackPan`

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
