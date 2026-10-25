---
title: "plugins.getPresetCount"
description: "Reference card for plugins.getPresetCount in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to plugins Module](/docs/api/plugins/)

# `plugins.getPresetCount`

**Resource URI:** `studio://api/plugins/getPresetCount`

Retrieve total count of factory and user presets.

#### Signature

```python
def getPresetCount(index: int, slot: int = -1) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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
