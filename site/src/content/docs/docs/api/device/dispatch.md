---
title: "device.dispatch"
description: "Reference card for device.dispatch in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.dispatch`

**Resource URI:** `studio://api/device/dispatch`

Dispatch internal hardware controller event message.

#### Signature

```python
def dispatch(messageId: int, value: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `messageId` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |

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
