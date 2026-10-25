---
title: "transport.rewind"
description: "Reference card for transport.rewind in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.rewind`

**Resource URI:** `studio://api/transport/rewind`

Engage rewind transport motion.

#### Signature

```python
def rewind(value: int = 2, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `int` | Yes | — | API v1 | — |
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
