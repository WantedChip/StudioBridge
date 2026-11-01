# transport.markerJump

**Resource URI:** `studio://api/transport/markerJump`

## Signature

```python
def markerJump(step: int, select: int = 0) -> None: ...
```

## Summary

Jump playback to the previous or next timeline marker.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `step` | `int` | No | — | API v1 | — |
| `select` | `int` | Yes | — | API v1 | — |

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
