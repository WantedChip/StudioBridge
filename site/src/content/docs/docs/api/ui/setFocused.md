---
title: "ui.setFocused"
description: "Reference card for ui.setFocused in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to ui Module](/docs/api/ui/)

# `ui.setFocused`

**Resource URI:** `studio://api/ui/setFocused`

Direct focus to the specified workspace window.

#### Signature

```python
def setFocused(window: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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
