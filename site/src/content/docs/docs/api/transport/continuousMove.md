---
title: "transport.continuousMove"
description: "Reference card for transport.continuousMove in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.continuousMove`

**Resource URI:** `studio://api/transport/continuousMove`

Move the song playback position continuously.

#### Signature

```python
def continuousMove(value: int, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `int` | No | — | API v1 | — |
| `step` | `int` | Yes | — | API v1 | — |

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
