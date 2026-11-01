# plugins.setParamValue

**Resource URI:** `studio://api/plugins/setParamValue`

## Signature

```python
def setParamValue(
    value: float,
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> None: ...
```

## Summary

Assign normalized automation value for plugin parameter.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `value` | `float` | No | `[0.0, 1.0]` | API v1 | — |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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
