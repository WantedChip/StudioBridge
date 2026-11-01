# transport.globalTransport

**Resource URI:** `studio://api/transport/globalTransport`

## Signature

```python
def globalTransport(command: int, value: int = 0) -> int: ...
```

## Summary

Dispatch a global transport action code.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `command` | `int` | No | — | API v1 | — |
| `value` | `int` | Yes | — | API v1 | — |

## Return Value

- **Type:** `int`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | None |
| Undo Mode | `none` |
| Execution Plane | `live` |
