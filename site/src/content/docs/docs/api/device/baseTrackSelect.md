---
title: "device.baseTrackSelect"
description: "Reference card for device.baseTrackSelect in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.baseTrackSelect`

**Resource URI:** `studio://api/device/baseTrackSelect`

Offset active track bank on hardware controller.

#### Signature

```python
def baseTrackSelect(offset: int, step: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `offset` | `int` | No | — | API v1 | — |
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
