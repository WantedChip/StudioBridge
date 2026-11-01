# device.forwardMIDICC

**Resource URI:** `studio://api/device/forwardMIDICC`

## Signature

```python
def forwardMIDICC(
    status: int,
    data1: int,
    data2: int,
) -> None: ...
```

## Summary

Forward raw MIDI Continuous Controller message to host.

## Parameters

| Parameter | Type | Optional | Range | Since | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `status` | `int` | No | — | API v1 | — |
| `data1` | `int` | No | — | API v1 | — |
| `data2` | `int` | No | — | API v1 | — |

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
