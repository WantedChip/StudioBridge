# mixer.isTrackSolo

**Resource URI:** `studio://api/mixer/isTrackSolo`

## Signature

```python
def isTrackSolo(index: int) -> bool: ...
```

## Summary

Query whether mixer track is soloed.

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
