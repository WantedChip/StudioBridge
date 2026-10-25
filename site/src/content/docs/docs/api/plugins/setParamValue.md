---
title: "plugins.setParamValue"
description: "Reference card for plugins.setParamValue in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to plugins Module](/docs/api/plugins/)

# `plugins.setParamValue`

**Resource URI:** `studio://api/plugins/setParamValue`

Assign normalized automation value for plugin parameter.

#### Signature

```python
def setParamValue(
    value: float,
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `float` | No | `[0, 1]` | API v1 | — |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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
