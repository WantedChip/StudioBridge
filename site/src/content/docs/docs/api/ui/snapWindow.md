---
title: "ui.snapWindow"
description: "Reference card for ui.snapWindow in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to ui Module](/docs/api/ui/)

# `ui.snapWindow`

**Resource URI:** `studio://api/ui/snapWindow`

Snap window position to preset desktop docking grid.

#### Signature

```python
def snapWindow(window: int, mode: int) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |
| `mode` | `int` | No | — | API v1 | — |

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
