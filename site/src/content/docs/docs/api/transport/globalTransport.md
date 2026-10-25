---
title: "transport.globalTransport"
description: "Reference card for transport.globalTransport in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.globalTransport`

**Resource URI:** `studio://api/transport/globalTransport`

Dispatch a global transport action code.

#### Signature

```python
def globalTransport(command: int, value: int = 0) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `command` | `int` | No | — | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `int`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |
