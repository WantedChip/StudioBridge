---
title: "mixer.setTrackColor"
description: "Reference card for mixer.setTrackColor in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.setTrackColor`

**Resource URI:** `studio://api/mixer/setTrackColor`

Assign display color for mixer track.

#### Signature

```python
def setTrackColor(index: int, color: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `color` | `int` | No | — | API v1 | — |

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
