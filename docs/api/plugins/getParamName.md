# plugins.getParamName

**Resource URI:** `studio://api/plugins/getParamName`

## Signature

```python
def getParamName(
    paramIndex: int,
    index: int,
    slot: int = -1,
) -> str: ...
```

## Summary

Retrieve name of automatable parameter.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `paramIndex` | `int` | No | — | API v1 | — |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

## Return Value

- **Type:** `str`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | No |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
