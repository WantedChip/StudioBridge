---
title: "device.processMIDICC"
description: "Reference card for device.processMIDICC in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.processMIDICC`

**Resource URI:** `studio://api/device/processMIDICC`

Process incoming MIDI CC through active mapping table.

#### Signature

```python
def processMIDICC(event: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event` | `int` | No | — | API v1 | — |

#### Return Value

- **Type:** `int`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |
