---
title: "channels.setChannelPan"
description: "Reference card for channels.setChannelPan in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.setChannelPan`

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
