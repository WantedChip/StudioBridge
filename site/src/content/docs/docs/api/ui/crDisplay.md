---
title: "ui.crDisplay"
description: "Reference card for ui.crDisplay in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to ui Module](/docs/api/ui/)

# `ui.crDisplay`

**Resource URI:** `studio://api/ui/crDisplay`

Update channel rack display control.

#### Signature

```python
def crDisplay(
    index: int,
    value: int,
    mode: int = 0,
) -> None: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `mode` | `int` | Yes | — | API v1 | — |

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
