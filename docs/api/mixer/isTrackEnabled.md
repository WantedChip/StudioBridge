# mixer.isTrackEnabled

**Resource URI:** `studio://api/mixer/isTrackEnabled`

## Signature

```python
def isTrackEnabled(index: int) -> bool: ...
```

## Summary

Query whether mixer track is active and processing audio.

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
