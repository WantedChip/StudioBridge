---
title: "channels.getChannelPan"
description: "Reference card for channels.getChannelPan in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.getChannelPan`

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
