# mixer.muteTrack

**Resource URI:** `studio://api/mixer/muteTrack`

## Signature

```python
def muteTrack(index: int, value: int = -1) -> None: ...
```

## Summary

Toggle or set mute state for mixer track.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `isTrackMuted`, compare: `exact`, settle: `immediate`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
