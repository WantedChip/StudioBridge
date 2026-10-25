---
title: "patterns.setPatternColor"
description: "Reference card for patterns.setPatternColor in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to patterns Module](/docs/api/patterns/)

# `patterns.setPatternColor`

**Resource URI:** `studio://api/patterns/setPatternColor`

Assign display color for pattern.

#### Signature

```python
def setPatternColor(index: int, color: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `color` | `int` | No | — | API v1 | — |

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
