# device.dispatch

**Resource URI:** `studio://api/device/dispatch`

## Signature

```python
def dispatch(messageId: int, value: int) -> None: ...
```

## Summary

Dispatch internal hardware controller event message.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `messageId` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
