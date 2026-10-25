---
title: "transport.setSongPos"
description: "Reference card for transport.setSongPos in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.setSongPos`

**Resource URI:** `studio://api/transport/setSongPos`

Set the normalized playback cursor position.

#### Signature

```python
def setSongPos(pos: float) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pos` | `float` | No | `[0, 1]` | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `getSongPos`, compare: `approx`, settle: `idle1ms`, tol: `0.01`, args: `[]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |
