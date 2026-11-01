# patterns.setPatternColor

**Resource URI:** `studio://api/patterns/setPatternColor`

## Signature

```python
def setPatternColor(index: int, color: int) -> None: ...
```

## Summary

Assign display color for pattern.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |
| `color` | `int` | No | — | API v1 | — |

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
