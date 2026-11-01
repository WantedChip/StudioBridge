# mixer.setTrackVolume

**Resource URI:** `studio://api/mixer/setTrackVolume`

## Signature

```python
def setTrackVolume(
    index: int,
    volume: float,
    pickupMode: int = 0,
) -> None: ...
```

## Summary

Set output volume level for mixer track.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `volume` | `float` | No | `[0.0, 1.0]` | API v1 | — |
| `pickupMode` | `int` | Yes | — | API v16 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getTrackVolume`, compare: `approx`, settle: `idle1`, tol: `0.005`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
