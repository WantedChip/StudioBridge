# channels.setChannelName

**Resource URI:** `studio://api/channels/setChannelName`

## Signature

```python
def setChannelName(index: int, name: str) -> None: ...
```

## Summary

Assign name label for channel.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |
| `name` | `str` | No | — | API v1 | — |

## Return Value

- **Type:** `None`

## Metadata

| Property | Value |
| :--- | :--- |
| Since API Version | API v1 |
| Mutating | Yes |
| Protected | No |
| Verification | getter: `getChannelName`, compare: `exact`, settle: `immediate`, args: `['$0']` |
| Undo Mode | `none` |
| Execution Plane | `live` |
