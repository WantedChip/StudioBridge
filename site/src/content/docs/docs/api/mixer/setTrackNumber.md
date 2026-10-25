---
title: "mixer.setTrackNumber"
description: "Reference card for mixer.setTrackNumber in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.setTrackNumber`

**Resource URI:** `studio://api/mixer/setTrackNumber`

Assign track index routing for mixer track.

#### Signature

```python
def setTrackNumber(index: int, number: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `number` | `int` | No | — | API v1 | — |

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
