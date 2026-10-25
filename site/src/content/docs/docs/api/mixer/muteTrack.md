---
title: "mixer.muteTrack"
description: "Reference card for mixer.muteTrack in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to mixer Module](/docs/api/mixer/)

# `mixer.muteTrack`

**Resource URI:** `studio://api/mixer/muteTrack`

Toggle or set mute state for mixer track.

#### Signature

```python
def muteTrack(index: int, value: int = -1) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `None`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | getter: `isTrackMuted`, compare: `exact`, settle: `immediatems`, args: `["$0"]` |
| Undo Mode | `none` |
| Execution Plane | `midi` |
