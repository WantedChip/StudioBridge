---
title: "transport.markerJump"
description: "Reference card for transport.markerJump in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.markerJump`

**Resource URI:** `studio://api/transport/markerJump`

Jump playback to the previous or next timeline marker.

#### Signature

```python
def markerJump(step: int, select: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `step` | `int` | No | — | API v1 | — |
| `select` | `int` | Yes | — | API v1 | — |

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
