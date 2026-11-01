# device.midiOutSysex

**Resource URI:** `studio://api/device/midiOutSysex`

## Signature

```python
def midiOutSysex(data: bytes) -> None: ...
```

## Summary

Send raw SysEx byte sequence to hardware output port.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `data` | `bytes` | No | — | API v1 | — |

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
