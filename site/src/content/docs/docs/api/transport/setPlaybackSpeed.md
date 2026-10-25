---
title: "transport.setPlaybackSpeed"
description: "Reference card for transport.setPlaybackSpeed in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.setPlaybackSpeed`

**Resource URI:** `studio://api/transport/setPlaybackSpeed`

Set transport playback speed factor.

#### Signature

```python
def setPlaybackSpeed(speed: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `speed` | `float` | No | — | API v1 | — |

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
