---
title: "device.midiOutSysex"
description: "Reference card for device.midiOutSysex in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.midiOutSysex`

**Resource URI:** `studio://api/device/midiOutSysex`

Send raw SysEx byte sequence to hardware output port.

#### Signature

```python
def midiOutSysex(data: bytes) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `data` | `bytes` | No | — | API v1 | — |

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
