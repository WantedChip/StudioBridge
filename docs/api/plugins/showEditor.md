# plugins.showEditor

**Resource URI:** `studio://api/plugins/showEditor`

## Signature

```python
def showEditor(index: int, slot: int = -1) -> None: ...
```

## Summary

Toggle display of graphical user interface editor for plugin.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
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
