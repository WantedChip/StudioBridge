---
title: "patterns.getPatternLength"
description: "Reference card for patterns.getPatternLength in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to patterns Module](/docs/api/patterns/)

# `patterns.getPatternLength`

**Resource URI:** `studio://api/patterns/getPatternLength`

Retrieve total length in steps for pattern.

#### Signature

```python
def getPatternLength(index: int) -> int: ...
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
