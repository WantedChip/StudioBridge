---
title: "device.getPortNumber"
description: "Reference card for device.getPortNumber in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.getPortNumber`

**Resource URI:** `studio://api/device/getPortNumber`

Retrieve MIDI port index assigned to controller script.

#### Signature

```python
def getPortNumber() -> int: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `int`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |
