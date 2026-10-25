---
title: "channels.isChannelSolo"
description: "Reference card for channels.isChannelSolo in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.isChannelSolo`

**Resource URI:** `studio://api/channels/isChannelSolo`

Query whether channel is soloed in channel rack.

#### Signature

```python
def isChannelSolo(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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
