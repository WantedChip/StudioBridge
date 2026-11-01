# device.processMIDICC

**Resource URI:** `studio://api/device/processMIDICC`

## Signature

```python
def processMIDICC(event: int) -> int: ...
```

## Summary

Process incoming MIDI CC through active mapping table.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event` | `int` | No | — | API v1 | — |

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
