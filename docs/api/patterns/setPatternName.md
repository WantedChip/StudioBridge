# patterns.setPatternName

**Resource URI:** `studio://api/patterns/setPatternName`

## Signature

```python
def setPatternName(index: int, name: str) -> None: ...
```

## Summary

Assign name label for pattern.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getPatternName`, compare: `exact`, settle: `immediate`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
