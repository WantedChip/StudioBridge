# mixer.isTrackMuted

**Resource URI:** `studio://api/mixer/isTrackMuted`

## Signature

```python
def isTrackMuted(index: int) -> bool: ...
```

## Summary

Query whether mixer track output is muted.

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
