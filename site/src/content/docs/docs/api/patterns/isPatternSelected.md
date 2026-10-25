---
title: "patterns.isPatternSelected"
description: "Reference card for patterns.isPatternSelected in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to patterns Module](/docs/api/patterns/)

# `patterns.isPatternSelected`

**Resource URI:** `studio://api/patterns/isPatternSelected`

Query whether pattern is selected in picker.

#### Signature

```python
def isPatternSelected(index: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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
