---
title: "channels.incEventValue"
description: "Reference card for channels.incEventValue in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to channels Module](/docs/api/channels/)

# `channels.incEventValue`

**Resource URI:** `studio://api/channels/incEventValue`

Increment or decrement channel event automation parameter.

#### Signature

```python
def incEventValue(
    eventId: int,
    value: int,
    step: int = 0,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventId` | `int` | No | — | API v1 | — |
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
