# general.saveUndo

**Resource URI:** `studio://api/general/saveUndo`

## Signature

```python
def saveUndo(name: str, flags: int = 0) -> None: ...
```

## Summary

Push a labeled transaction checkpoint into undo history.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `name` | `str` | No | — | API v1 | — |
| `flags` | `int` | Yes | — | API v1 | — |

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
