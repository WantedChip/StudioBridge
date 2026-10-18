"""_sb_wire.py - Pure Python 3.9 SysEx frame codec, CRC-16, and septet packing.

Zero external dependencies. Compatible with FL Studio embedded Python sandbox.
"""

SYSEX_START = 0xF0
MANUFACTURER_ID = 0x7D
MAGIC = b"SB"
PROTOCOL_VERSION = 0x01
SYSEX_END = 0xF7

KIND_REQ = 1
KIND_RES = 2
KIND_EVT = 3
KIND_CTL = 4

FLAG_NONE = 0
FLAG_ENC_JSON = 2

FRAME_OVERHEAD = 22  # 18 header + 4 tail


def _make_crc_table():
    table = []
    for i in range(256):
        curr = i << 8
        for _ in range(8):
            curr = ((curr << 1) ^ 0x1021) & 0xFFFF if curr & 0x8000 else (curr << 1) & 0xFFFF
        table.append(curr)
    return table


_CRC_TABLE = _make_crc_table()


def crc16(data, init=0xFFFF):
    """Calculate CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection)."""
    crc = init & 0xFFFF
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _CRC_TABLE[(crc >> 8) ^ (b & 0xFF)]
    return crc & 0xFFFF


def pack_14(val):
    """Pack a 14-bit integer into 2 7-bit septets (big-endian)."""
    val = int(val) & 0x3FFF
    return bytes([(val >> 7) & 0x7F, val & 0x7F])


def unpack_14(b0, b1):
    """Unpack 2 7-bit septets into a 14-bit unsigned integer."""
    return ((b0 & 0x7F) << 7) | (b1 & 0x7F)


def pack_21(val):
    """Pack a 21-bit integer into 3 7-bit septets (big-endian)."""
    val = int(val) & 0x1FFFFF
    return bytes([(val >> 14) & 0x7F, (val >> 7) & 0x7F, val & 0x7F])


def unpack_21(b0, b1, b2):
    """Unpack 3 7-bit septets into a 21-bit unsigned integer."""
    return ((b0 & 0x7F) << 14) | ((b1 & 0x7F) << 7) | (b2 & 0x7F)


def pack_crc(crc):
    """Pack 16-bit CRC into 3 7-bit septets (2 + 7 + 7 bits)."""
    crc = int(crc) & 0xFFFF
    return bytes([(crc >> 14) & 0x03, (crc >> 7) & 0x7F, crc & 0x7F])


def unpack_crc(b0, b1, b2):
    """Unpack 3 7-bit septets into a 16-bit CRC integer."""
    return ((b0 & 0x03) << 14) | ((b1 & 0x7F) << 7) | (b2 & 0x7F)


def encode_frame(kind, flags, sid, mid, cidx, ccnt, payload, max_frame_size=None):
    """Encode discrete SysEx frame into raw bytes.

    Layout (22-byte framing overhead):
      [0]    0xF0 (SysEx Start)
      [1]    0x7D (Manufacturer ID)
      [2..3] 'S', 'B' (Magic)
      [4]    0x01 (Version)
      [5]    kind (1..4)
      [6]    flags (bit 1: JSON)
      [7..8] sid (14-bit)
      [9..11] mid (21-bit)
      [12..13] cidx (14-bit)
      [14..15] ccnt (14-bit)
      [16..17] payload_len (14-bit)
      [18..] payload (7-bit clean ASCII bytes)
      [-4..-2] CRC-16 (3 septets)
      [-1]   0xF7 (SysEx End)
    """
    if isinstance(payload, str):
        payload = payload.encode("ascii")
    elif not isinstance(payload, bytes):
        payload = bytes(payload)

    plen = len(payload)
    buf = bytearray()
    buf.append(SYSEX_START)
    buf.append(MANUFACTURER_ID)
    buf.extend(MAGIC)
    buf.append(PROTOCOL_VERSION)
    buf.append(int(kind) & 0x7F)
    buf.append(int(flags) & 0x7F)
    buf.extend(pack_14(sid))
    buf.extend(pack_21(mid))
    buf.extend(pack_14(cidx))
    buf.extend(pack_14(ccnt))
    buf.extend(pack_14(plen))
    buf.extend(payload)

    # CRC computed from byte 4 (PROTOCOL_VERSION) through last payload byte
    crc = crc16(buf[4:])
    buf.extend(pack_crc(crc))
    buf.append(SYSEX_END)

    result = bytes(buf)
    if max_frame_size is not None and len(result) > max_frame_size:
        raise ValueError(f"Frame length {len(result)} exceeds max_frame_size {max_frame_size}")
    return result


def decode_frame(raw):
    """Decode raw SysEx frame bytes into a dictionary of fields.

    Returns None if the frame is invalid, corrupted, or has a CRC mismatch.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw)

    raw_len = len(raw)
    if raw_len < FRAME_OVERHEAD:
        return None

    if raw[0] != SYSEX_START or raw[-1] != SYSEX_END:
        return None

    if raw[1] != MANUFACTURER_ID or raw[2] != MAGIC[0] or raw[3] != MAGIC[1]:
        return None

    if raw[4] != PROTOCOL_VERSION:
        return None

    # Check 7-bit cleanliness of all interior bytes
    for b in raw[1:-1]:
        if b >= 0x80:
            return None

    # Verify CRC
    expected_crc = crc16(raw[4:-4])
    actual_crc = unpack_crc(raw[-4], raw[-3], raw[-2])
    if actual_crc != expected_crc:
        return None

    kind = raw[5]
    flags = raw[6]
    sid = unpack_14(raw[7], raw[8])
    mid = unpack_21(raw[9], raw[10], raw[11])
    cidx = unpack_14(raw[12], raw[13])
    ccnt = unpack_14(raw[14], raw[15])
    plen = unpack_14(raw[16], raw[17])

    if ccnt < 1 or cidx >= ccnt:
        return None

    if FRAME_OVERHEAD + plen != raw_len:
        return None

    payload = bytes(raw[18 : 18 + plen])
    return {
        "kind": kind,
        "flags": flags,
        "sid": sid,
        "mid": mid,
        "cidx": cidx,
        "ccnt": ccnt,
        "payload_len": plen,
        "payload": payload,
        "crc": actual_crc,
    }


def chunk_payload(payload_bytes, max_chunk_size=490):
    """Split payload bytes into chunks of at most max_chunk_size bytes."""
    if isinstance(payload_bytes, str):
        payload_bytes = payload_bytes.encode("ascii")
    elif not isinstance(payload_bytes, bytes):
        payload_bytes = bytes(payload_bytes)

    if not payload_bytes:
        return [b""]

    chunks = []
    for i in range(0, len(payload_bytes), max_chunk_size):
        chunks.append(payload_bytes[i : i + max_chunk_size])
    return chunks


class WireReassembler:
    """Device-side multi-chunk payload reassembler with bounded memory."""

    def __init__(self, max_messages=16):
        self.max_messages = max_messages
        self._buffers = {}
        self._order = []

    def add_chunk(self, frame):
        """Add a frame to the reassembly buffer.

        Returns full payload bytes when all chunks are collected, or None if pending.
        """
        cidx = frame["cidx"]
        ccnt = frame["ccnt"]
        payload = frame["payload"]

        if ccnt == 1:
            return payload

        key = (frame["kind"], frame["sid"], frame["mid"])
        if key not in self._buffers:
            if len(self._buffers) >= self.max_messages:
                oldest = self._order.pop(0)
                self._buffers.pop(oldest, None)
            self._buffers[key] = {"ccnt": ccnt, "chunks": {cidx: payload}}
            self._order.append(key)
        else:
            self._buffers[key]["chunks"][cidx] = payload

        buf = self._buffers[key]
        if len(buf["chunks"]) == ccnt:
            # Reconstruct in chunk order
            assembled = b"".join(buf["chunks"][i] for i in range(ccnt))
            self._buffers.pop(key, None)
            if key in self._order:
                self._order.remove(key)
            return assembled

        return None
