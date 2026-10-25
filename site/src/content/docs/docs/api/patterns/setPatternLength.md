---
title: "patterns.setPatternLength"
description: "Reference card for patterns.setPatternLength in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to patterns Module](/docs/api/patterns/)

# `patterns.setPatternLength`

**Resource URI:** `studio://api/patterns/setPatternLength`

Set total length in steps for pattern.

#### Signature

```python
def setPatternLength(index: int, length: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `length` | `int` | No | — | API v1 | — |

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
