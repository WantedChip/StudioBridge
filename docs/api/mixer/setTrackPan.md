# mixer.setTrackPan

**Resource URI:** `studio://api/mixer/setTrackPan`

## Signature

```python
def setTrackPan(index: int, pan: float) -> None: ...
```

## Summary

Set stereo pan position for mixer track.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `pan` | `float` | No | `[-1.0, 1.0]` | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getTrackPan`, compare: `approx`, settle: `idle1`, tol: `0.005`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
