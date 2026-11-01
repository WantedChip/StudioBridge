# transport.getSongLength

**Resource URI:** `studio://api/transport/getSongLength`

## Signature

```python
def getSongLength(mode: int = 0) -> float: ...
```

## Summary

Retrieve total song length in beats or seconds.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | Yes | — | API v1 | — |

## Return Value

- **Type:** `float`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
