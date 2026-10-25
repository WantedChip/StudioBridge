---
title: "transport.getSongLength"
description: "Reference card for transport.getSongLength in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.getSongLength`

**Resource URI:** `studio://api/transport/getSongLength`

Retrieve total song length in beats or seconds.

#### Signature

```python
def getSongLength(mode: int = 0) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | Yes | — | API v1 | — |

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
