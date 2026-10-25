---
title: "ui.getVisibleForm"
description: "Reference card for ui.getVisibleForm in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to ui Module](/docs/api/ui/)

# `ui.getVisibleForm`

**Resource URI:** `studio://api/ui/getVisibleForm`

Query whether floating tool form is currently visible.

#### Signature

```python
def getVisibleForm(formId: int) -> bool: ...
```

#### Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `formId` | `int` | No | — | API v1 | — |

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
