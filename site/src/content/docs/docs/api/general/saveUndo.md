---
title: "general.saveUndo"
description: "Reference card for general.saveUndo in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to general Module](/docs/api/general/)

# `general.saveUndo`

**Resource URI:** `studio://api/general/saveUndo`

Push a labeled transaction checkpoint into undo history.

#### Signature

```python
def saveUndo(name: str, flags: int = 0) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `name` | `str` | No | — | API v1 | — |
| `flags` | `int` | Yes | — | API v1 | — |

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
