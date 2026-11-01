# channels.getChannelPan

**Resource URI:** `studio://api/channels/getChannelPan`

## Signature

```python
def getChannelPan(index: int) -> float: ...
```

## Summary

Retrieve stereo pan value for channel.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `index` | `int` | No | `[0, 999]` | API v1 | — |

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
