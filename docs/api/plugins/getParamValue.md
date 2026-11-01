# plugins.getParamValue

**Resource URI:** `studio://api/plugins/getParamValue`

## Signature

```python
def getParamValue(
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> float: ...
```

## Summary

Retrieve normalized value (0.0-1.0) of automatable parameter.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

## Return Value

- **Type:** `float`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
