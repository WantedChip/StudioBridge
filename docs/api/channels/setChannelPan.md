# channels.setChannelPan

**Resource URI:** `studio://api/channels/setChannelPan`

## Signature

```python
def setChannelPan(index: int, pan: float) -> None: ...
```

## Summary

Set stereo pan position for channel.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `pan` | `float` | No | `[-1.0, 1.0]` | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getChannelPan`, compare: `approx`, settle: `idle1`, tol: `0.005`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
