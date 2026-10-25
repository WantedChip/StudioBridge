---
title: "channels.getChannelPitch"
description: "Reference card for channels.getChannelPitch in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.getChannelPitch`

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
