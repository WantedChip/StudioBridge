# channels.incEventValue

**Resource URI:** `studio://api/channels/incEventValue`

## Signature

```python
def incEventValue(
    eventId: int,
    value: int,
    step: int = 0,
) -> None: ...
```

## Summary

Increment or decrement channel event automation parameter.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventId` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `step` | `int` | Yes | — | API v1 | — |

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
