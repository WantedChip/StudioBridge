---
title: "mixer.linkTrackToChannel"
description: "Reference card for mixer.linkTrackToChannel in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.linkTrackToChannel`

**Resource URI:** `studio://api/mixer/linkTrackToChannel`

Route active channel directly to selected mixer track.

#### Signature

```python
def linkTrackToChannel(mode: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | No | — | API v1 | — |

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
