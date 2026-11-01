# channels.channelCount

**Resource URI:** `studio://api/channels/channelCount`

## Signature

```python
def channelCount(mode: int = 0) -> int: ...
```

## Summary

Return the total count of generator and sampler channels.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `int` | Yes | — | API v1 | — |

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
