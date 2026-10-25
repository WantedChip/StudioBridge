---
title: "plugins.getPresetName"
description: "Reference card for plugins.getPresetName in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to plugins Module](/docs/api/plugins/)

# `plugins.getPresetName`

**Resource URI:** `studio://api/plugins/getPresetName`

Retrieve preset title for given preset index.

#### Signature

```python
def getPresetName(
    presetIndex: int,
    index: int,
    slot: int = -1,
) -> str: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `presetIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

#### Return Value

- **Type:** `str`

#### Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected Target | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `midi` |
