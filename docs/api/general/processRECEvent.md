# general.processRECEvent

**Resource URI:** `studio://api/general/processRECEvent`

## Signature

```python
def processRECEvent(
    eventId: int,
    value: int,
    flags: int = 0,
) -> int: ...
```

## Summary

Dispatch automation recording event.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventId` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `flags` | `int` | Yes | — | API v1 | — |

## Return Value

- **Type:** `int`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
