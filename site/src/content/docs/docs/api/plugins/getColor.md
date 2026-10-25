---
title: "plugins.getColor"
description: "Reference card for plugins.getColor in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to plugins Module](/docs/api/plugins/)

# `plugins.getColor`

**Resource URI:** `studio://api/plugins/getColor`

Retrieve color code for plugin instance.

#### Signature

```python
def getColor(index: int, slot: int = -1) -> int: ...
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
