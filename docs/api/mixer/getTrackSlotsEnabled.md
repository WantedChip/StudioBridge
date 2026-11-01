# mixer.getTrackSlotsEnabled

**Resource URI:** `studio://api/mixer/getTrackSlotsEnabled`

## Signature

```python
def getTrackSlotsEnabled(index: int) -> bool: ...
```

## Summary

Query whether effect slots are enabled on mixer track.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

## Return Value

- **Type:** `bool`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
