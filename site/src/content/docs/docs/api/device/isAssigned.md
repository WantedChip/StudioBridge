---
title: "device.isAssigned"
description: "Reference card for device.isAssigned in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to device Module](/docs/api/device/)

# `device.isAssigned`

**Resource URI:** `studio://api/device/isAssigned`

Query whether controller script is linked to a valid port.

#### Signature

```python
def isAssigned() -> bool: ...
```

#### Parameters

This function takes no parameters.

#### Return Value

- **Type:** `bool`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |
