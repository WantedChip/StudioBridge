# channels.setTargetFxTrack

**Resource URI:** `studio://api/channels/setTargetFxTrack`

## Signature

```python
def setTargetFxTrack(index: int, track: int) -> None: ...
```

## Summary

Assign target mixer insert track for channel.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `track` | `int` | No | `[0, 126]` | API v1 | — |

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
