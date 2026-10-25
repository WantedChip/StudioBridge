---
title: "general.processRECEvent"
description: "Reference card for general.processRECEvent in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to general Module](/docs/api/general/)

# `general.processRECEvent`

**Resource URI:** `studio://api/general/processRECEvent`

Dispatch automation recording event.

#### Signature

```python
def processRECEvent(
    eventId: int,
    value: int,
    flags: int = 0,
) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventId` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `flags` | `int` | Yes | — | API v1 | — |

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
