---
title: "channels.setChannelName"
description: "Reference card for channels.setChannelName in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.setChannelName`

**Resource URI:** `studio://api/channels/setChannelName`

Assign name label for channel.

#### Signature

```python
def setChannelName(index: int, name: str) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getChannelName`, compare: `exact`, settle: `immediatems`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |
