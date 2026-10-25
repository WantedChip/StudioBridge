---
title: "channels.setTargetFxTrack"
description: "Reference card for channels.setTargetFxTrack in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.setTargetFxTrack`

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
