# device.midiOutMsg

**Resource URI:** `studio://api/device/midiOutMsg`

## Signature

```python
def midiOutMsg(message: int) -> None: ...
```

## Summary

Send short 3-byte MIDI message to hardware output port.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `message` | `int` | No | — | API v1 | — |

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
