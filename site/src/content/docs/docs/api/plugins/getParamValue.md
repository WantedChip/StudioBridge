---
title: "plugins.getParamValue"
description: "Reference card for plugins.getParamValue in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to plugins Module](/docs/api/plugins/)

# `plugins.getParamValue`

**Resource URI:** `studio://api/plugins/getParamValue`

Retrieve normalized value (0.0-1.0) of automatable parameter.

#### Signature

```python
def getParamValue(
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> float: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `float`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |
