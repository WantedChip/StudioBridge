# channels.setChannelVolume

**Resource URI:** `studio://api/channels/setChannelVolume`

## Signature

```python
def setChannelVolume(index: int, volume: float) -> None: ...
```

## Summary

Set volume level for channel.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `volume` | `float` | No | `[0.0, 1.0]` | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getChannelVolume`, compare: `approx`, settle: `idle1`, tol: `0.005`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
