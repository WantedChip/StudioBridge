---
title: "ui.hideWindow"
description: "Reference card for ui.hideWindow in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to ui Module](/docs/api/ui/)

# `ui.hideWindow`

**Resource URI:** `studio://api/ui/hideWindow`

Hide the designated FL Studio workspace window.

#### Signature

```python
def hideWindow(window: int) -> None: ...
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
