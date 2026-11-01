# ui.crDisplay

**Resource URI:** `studio://api/ui/crDisplay`

## Signature

```python
def crDisplay(
    index: int,
    value: int,
    mode: int = 0,
) -> None: ...
```

## Summary

Update channel rack display control.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | — | API v1 | — |
| `value` | `int` | No | — | API v1 | — |
| `mode` | `int` | Yes | — | API v1 | — |

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
