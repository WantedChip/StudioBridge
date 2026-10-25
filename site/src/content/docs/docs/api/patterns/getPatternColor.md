---
title: "patterns.getPatternColor"
description: "Reference card for patterns.getPatternColor in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to patterns Module](/docs/api/patterns/)

# `patterns.getPatternColor`

**Resource URI:** `studio://api/patterns/getPatternColor`

Retrieve RGB color code for pattern.

#### Signature

```python
def getPatternColor(index: int) -> int: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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
