---
title: "SysEx Wire Protocol Specification"
description: "Authoritative technical specification of the StudioBridge MIDI System Exclusive (SysEx) wire protocol."
---

StudioBridge establishes a reliable, bidirectional RPC channel over standard MIDI 1.0 System Exclusive (SysEx) streams.

Because standard MIDI SysEx restricts data bytes to the 7-bit range (`0x00`–`0x7F`), StudioBridge implements framing, bit-packing, sequencing, CRC-16 error checking, and chunk reassembly.

---

## 1. Frame Structure

Every transmission is enclosed in a standard MIDI SysEx frame:

```
+------+------+-----------+------+-----+------+-------+--------+---------+------+------+
| SOF  | MFR  |   MAGIC   | VER  | SEQ | OP   | TOTAL | CHUNK  | PAYLOAD | CRC  | EOF  |
| 0xF0 | 0x7D | 0x53 0x42 | 0x01 | 7b  | 7b   | 7b    | 7b     | 7b data | 14b  | 0xF7 |
+------+------+-----------+------+-----+------+-------+--------+---------+------+------+
  1B     1B        2B       1B    1B    1B     1B      1B       Var       2B     1B
```

### Field Definitions

| Offset | Field | Size | Allowed Values | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0` | **SOF** | 1 byte | `0xF0` | Standard MIDI System Exclusive Start. |
| `1` | **Manufacturer ID** | 1 byte | `0x7D` | MIDI Educational / Research Non-Commercial ID. |
| `2..3` | **Magic Bytes** | 2 bytes | `0x53 0x42` | ASCII characters `'S'` (`0x53`) and `'B'` (`0x42`) for StudioBridge. |
| `4` | **Protocol Version** | 1 byte | `0x01` | Protocol revision counter (currently Version 1). |
| `5` | **Sequence ID** | 1 byte | `0x00`–`0x7F` | 7-bit rolling packet sequence counter for drop detection. |
| `6` | **Opcode** | 1 byte | `0x01`–`0x7F` | Command or response operation code. |
| `7` | **Total Chunks** | 1 byte | `0x01`–`0x7F` | Total number of chunks in this message. |
| `8` | **Chunk Index** | 1 byte | `0x00`–`0x7E` | Zero-based index of this specific chunk (`0` to `TOTAL - 1`). |
| `9..N-3` | **7-Bit Payload** | Variable | `0x00`–`0x7F` | 7-bit packed serialized payload (JSON or binary RPC). |
| `N-2..N-1` | **CRC-16** | 2 bytes | `0x00`–`0x7F` | CRC-16 CCITT split into two 7-bit words (`MSB_7`, `LSB_7`). |
| `N` | **EOF** | 1 byte | `0xF7` | Standard MIDI System Exclusive End. |

---

## 2. 7-Bit Payload Encoding (7-to-8 Bit Packing)

Standard MIDI transmissions disallow bytes with the most significant bit set (`0x80`–`0xFF`). To transmit arbitrary 8-bit binary data (such as UTF-8 JSON payloads), StudioBridge packs every 7 eight-bit bytes into 8 seven-bit words:

### Packing Algorithm
For every group of 7 data bytes `[d0, d1, d2, d3, d4, d5, d6]`:
1. The 7 most significant bits (MSBs) of the 7 bytes are extracted into a single prefix byte `h`:
   ```
   h = ((d0 & 0x80) >> 1) | ((d1 & 0x80) >> 2) | ((d2 & 0x80) >> 3) |
       ((d3 & 0x80) >> 4) | ((d4 & 0x80) >> 5) | ((d5 & 0x80) >> 6) |
       ((d6 & 0x80) >> 7)
   ```
2. The remaining lower 7 bits of each byte are stored as seven subsequent bytes:
   ```
   [h, d0 & 0x7F, d1 & 0x7F, d2 & 0x7F, d3 & 0x7F, d4 & 0x7F, d5 & 0x7F, d6 & 0x7F]
   ```
3. All 8 transmitted bytes are guaranteed to be in the range `0x00`–`0x7F`.

---

## 3. CRC-16 CCITT Integrity Check

To guarantee that frame corruption or truncated loopback buffers never result in undefined DAW mutations, every frame terminates with a 16-bit CRC:

- **Polynomial:** `0x1021` (CRC-16 CCITT, initial value `0xFFFF`).
- **Input Scope:** Computed over all bytes from `Protocol Version` (offset 4) through the end of the `7-Bit Payload`.
- **7-Bit Transmission:** The 16-bit CRC value is serialized as two 7-bit words:
  ```
  crc_msb = (crc >> 7) & 0x7F
  crc_lsb = crc & 0x7F
  ```
If the calculated CRC does not match upon receipt, the frame is discarded and an `ERR_BAD_CRC` error is returned.

---

## 4. Packet Chunking & Reassembly

FL Studio's controller script runtime imposes a maximum single-message SysEx buffer limit of **512 bytes**. Payloads exceeding this threshold (e.g. detailed channel rack listings or large pattern states) are split across multiple chunks:

```
[Packet 0: Total=3, Chunk=0] -> [Packet 1: Total=3, Chunk=1] -> [Packet 2: Total=3, Chunk=2]
```

### Reassembly Rules
1. **Reassembly Buffer:** The receiver maintains an active reassembly buffer keyed by `(Sequence ID, Opcode)`.
2. **Order Enforcement:** Chunks must arrive sequentially (`0`, `1`, `...`, `TOTAL - 1`). If a chunk index is skipped, a sequence gap error (`ERR_SEQ_GAP`) is triggered.
3. **Reassembly Timeout:** If all chunks are not received within **500ms**, the partial buffer is purged.

---

## 5. Opcode Directory

| Opcode | Hex | Direction | Payload | Description |
| :--- | :--- | :--- | :--- | :--- |
| **HELLO** | `0x01` | Host ↔ Device | JSON `{ client, version }` | Initial handshake and protocol capability negotiation. |
| **RPC_CALL** | `0x02` | Host → Device | JSON `{ id, module, fn, args }` | Dispatch an API method call to FL Studio. |
| **RPC_RESP** | `0x03` | Device → Host | JSON `{ id, ok, result, error }` | Return result or error receipt from executed method. |
| **HEARTBEAT** | `0x04` | Host ↔ Device | Timestamp (4 bytes) | Periodic keepalive ping sent every 1000ms. |
| **ERROR** | `0x05` | Device → Host | JSON `{ id, code, message }` | Fatal wire or framing error notification. |
| **MUTATION_NOTIFY** | `0x06` | Device → Host | JSON `{ target, old_val, new_val }` | Host state mutation event notification. |
| **RESET** | `0x0F` | Host → Device | Empty | Force reset of script reassembly buffers and state. |

---

## 6. Error Codes

| Code | Value | Meaning | Recovery Action |
| :--- | :--- | :--- | :--- |
| `ERR_BAD_MAGIC` | `0x10` | Frame missing `0x53 0x42` magic bytes. | Verify MIDI port routing; check for interfering controllers. |
| `ERR_BAD_VERSION`| `0x11` | Incompatible protocol version. | Update `studiobridge` CLI and reinstall controller script. |
| `ERR_BAD_CRC` | `0x12` | CRC-16 checksum verification failed. | Resend frame; check for loopback driver packet drop. |
| `ERR_SEQ_GAP` | `0x13` | Missing chunk detected in sequence. | Receiver aborts reassembly; host initiates retry. |
| `ERR_TIMEOUT` | `0x14` | RPC call timed out without response. | Check FL Studio UI responsiveness; verify script is active. |
| `ERR_DISALLOWED`| `0x15` | Mutating call attempted in read-only mode. | Request safety authorization elevation before writing. |
