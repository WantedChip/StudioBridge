---
title: "mixer.getTrackSlotsEnabled"
description: "Reference card for mixer.getTrackSlotsEnabled in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.getTrackSlotsEnabled`

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
