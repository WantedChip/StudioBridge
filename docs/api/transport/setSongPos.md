# transport.setSongPos

**Resource URI:** `studio://api/transport/setSongPos`

## Signature

```python
def setSongPos(pos: float) -> None: ...
```

## Summary

Set the normalized playback cursor position.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pos` | `float` | No | `[0.0, 1.0]` | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getSongPos`, compare: `approx`, settle: `idle1`, tol: `0.01` |
| Undo Mode | `none` |
| Execution Plane | `live` |
