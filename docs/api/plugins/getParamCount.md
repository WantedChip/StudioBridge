# plugins.getParamCount

**Resource URI:** `studio://api/plugins/getParamCount`

## Signature

```python
def getParamCount(index: int, slot: int = -1) -> int: ...
```

## Summary

Retrieve total count of automatable parameters in plugin.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `slot` | `int` | Yes | — | API v1 | — |

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
