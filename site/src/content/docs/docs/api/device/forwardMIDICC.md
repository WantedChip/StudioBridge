---
title: "device.forwardMIDICC"
description: "Reference card for device.forwardMIDICC in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.forwardMIDICC`

**Resource URI:** `studio://api/device/forwardMIDICC`

Forward raw MIDI Continuous Controller message to host.

#### Signature

```python
def forwardMIDICC(
    status: int,
    data1: int,
    data2: int,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `status` | `int` | No | — | API v1 | — |
| `data1` | `int` | No | — | API v1 | — |
| `data2` | `int` | No | — | API v1 | — |

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
