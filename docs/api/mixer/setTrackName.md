# mixer.setTrackName

**Resource URI:** `studio://api/mixer/setTrackName`

## Signature

```python
def setTrackName(index: int, name: str) -> None: ...
```

## Summary

Assign descriptive label for mixer track.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 126]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getTrackName`, compare: `exact`, settle: `immediate`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
