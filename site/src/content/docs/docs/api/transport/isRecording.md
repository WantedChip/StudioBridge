---
title: "transport.isRecording"
description: "Reference card for transport.isRecording in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to transport Module](/docs/api/transport/)

# `transport.isRecording`

**Resource URI:** `studio://api/transport/isRecording`

Query whether transport recording mode is active.

#### Signature

```python
def isRecording() -> bool: ...
```

#### Parameters

This function takes no parameters.

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
