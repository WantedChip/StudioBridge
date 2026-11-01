# channels.isChannelMuted

**Resource URI:** `studio://api/channels/isChannelMuted`

## Signature

```python
def isChannelMuted(index: int) -> bool: ...
```

## Summary

Query whether channel audio generation is muted.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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
