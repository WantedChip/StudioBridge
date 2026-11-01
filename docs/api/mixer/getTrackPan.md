# mixer.getTrackPan

**Resource URI:** `studio://api/mixer/getTrackPan`

## Signature

```python
def getTrackPan(index: int) -> float: ...
```

## Summary

Retrieve stereo panorama position for mixer track.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |

## Return Value

- **Type:** `float`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
