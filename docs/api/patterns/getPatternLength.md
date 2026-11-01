# patterns.getPatternLength

**Resource URI:** `studio://api/patterns/getPatternLength`

## Signature

```python
def getPatternLength(index: int) -> int: ...
```

## Summary

Retrieve total length in steps for pattern.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[1, 999]` | API v1 | — |

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
