# ui.getFocused

**Resource URI:** `studio://api/ui/getFocused`

## Signature

```python
def getFocused(window: int) -> bool: ...
```

## Summary

Query whether specified FL Studio window currently holds focus.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `window` | `int` | No | — | API v1 | — |

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
