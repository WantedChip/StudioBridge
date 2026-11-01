# channels.getTargetFxTrack

**Resource URI:** `studio://api/channels/getTargetFxTrack`

## Signature

```python
def getTargetFxTrack(index: int) -> int: ...
```

## Summary

Retrieve target mixer insert track routed for channel.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

## Return Value

- **Type:** `int`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
