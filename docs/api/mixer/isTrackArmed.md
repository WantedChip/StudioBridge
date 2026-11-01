# mixer.isTrackArmed

**Resource URI:** `studio://api/mixer/isTrackArmed`

## Signature

```python
def isTrackArmed(index: int) -> bool: ...
```

## Summary

Query whether mixer track is armed for disk recording.

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
