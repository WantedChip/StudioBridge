---
title: "device.midiOutMsg"
description: "Reference card for device.midiOutMsg in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.midiOutMsg`

**Resource URI:** `studio://api/device/midiOutMsg`

Send short 3-byte MIDI message to hardware output port.

#### Signature

```python
def midiOutMsg(message: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `message` | `int` | No | — | API v1 | — |

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
