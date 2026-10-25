---
title: "channels.getChannelColor"
description: "Reference card for channels.getChannelColor in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.getChannelColor`

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
