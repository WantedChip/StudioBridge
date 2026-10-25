# Clean-Room Provenance Registry for FLP Format

> **Requirement Reference:** `[FLP-60]`, `07_l0e_flp_engine.md §6`, `01_vision_scope.md §9`.

This document records the clean-room provenance and factual sources for the binary `.flp` container format and event stream codec implemented in StudioBridge.

---

## 1. Clean-Room Architectural Policy

1. **Zero GPL Code:** Upstream PyFLP is licensed under GNU General Public License v3.0 (GPL-3.0). PyFLP code, structures, variable names, or ASTs MUST NEVER be imported, vendored, decompiled, or ported into StudioBridge source packages or release wheels.
2. **Permissive Sources Only:** All format facts, structural definitions, and event ranges are derived exclusively from permissive open-source specifications (MIT, BSD, Apache 2.0) and black-box experiments on real project binaries produced by licensed FL Studio installations.
3. **Lossless Verification Invariant:** The binary codec (`studiobridge.flp.codec`) implements pure structural parsing without semantic interpretation. Round-trip serialization guarantees `serialize(parse(b)) == b` on 100% of tested corpus files.

---

## 2. Permissive Reference Corpus

The following independent, permissively licensed implementations and documentation were consulted as secondary references:

| Project | Language | License | Primary Author / Repository | Format Contributions |
|---|---|---|---|---|
| `flp-file` | JavaScript / Node.js | MIT | `j-f1/flp-file` | Chunk header layout (`FLhd`, `FLdt`), 7-bit little-endian varint decoding, 1/2/4-byte event range boundaries. |
| `FLParser` | C# / .NET | MIT | `monadgroup/FLParser` | Multi-chunk container structure, header field types (`format`, `channels`, `ppq`), variable-length string layouts. |
| `bravoh-daw` | Rust | MIT | Community repository | Stream slice decoding without semantic interpretation, memory-efficient event iteration. |
| **StudioBridge Hardware Corpus** | Binary | Proprietary / Fair Use Analysis | Author-created test projects (FL 21.0 through 26.1.x) | Non-canonical varint encodings, inter-chunk alignment padding, trailing byte preservation, FL 25/26 event behavior. |

---

## 3. Format Facts Registry

### 3.1 Container & Chunk Architecture

| Format Fact | Specification | Primary Source |
|---|---|---|
| **Container Magic** | Binary files begin with ASCII chunk identifier `FLhd` (0x46, 0x4C, 0x68, 0x64). | `flp-file`, corpus analysis |
| **Chunk Framing** | Each chunk consists of a 4-byte ASCII ID followed by a 32-bit unsigned little-endian integer (`<I`) indicating the chunk payload length in bytes. | `FLParser`, `flp-file` |
| **Header Chunk (`FLhd`)** | Standard payload length is ≥ 6 bytes. Contains: `format` (uint16 LE), `channels` (uint16 LE, channel rack count), `ppq` (uint16 LE, time division). | `flp-file`, corpus analysis |
| **Data Chunk (`FLdt`)** | Payload contains the sequential, byte-aligned stream of tagged event structures. Multiple `FLdt` chunks may occur in complex sessions. | `FLParser`, corpus analysis |
| **Alignment Padding** | Some historical versions or third-party tools align chunks to 2-byte or 4-byte boundaries with null padding (`\x00`). Codec preserves inter-chunk padding verbatim. | StudioBridge corpus experiments (`[FLP-03]`) |
| **Trailing Bytes** | Trailing data following the final declared chunk (e.g. metadata footers or digital signatures) are preserved verbatim without truncation. | StudioBridge corpus experiments (`[FLP-03]`) |

### 3.2 Event Classification & Framing

FLP event IDs are single-byte unsigned integers (`0–255`). The numeric range of the event ID strictly determines the size of the payload following the ID:

| Event ID Range | Payload Size | Framing Representation | Permissive Source |
|---|---|---|---|
| `0–63` (`0x00–0x3F`) | 1 byte | Single raw byte (boolean, small integer, mode flag). | `flp-file`, `bravoh-daw` |
| `64–127` (`0x40–0x7F`) | 2 bytes | 16-bit little-endian unsigned short (`<H`). | `flp-file`, `bravoh-daw` |
| `128–191` (`0x80–0xBF`) | 4 bytes | 32-bit little-endian unsigned integer (`<I`). | `flp-file`, `bravoh-daw` |
| `192–255` (`0xC0–0xFF`) | Variable | Preceded by 7-bit varint length prefix, followed by `length` bytes of raw payload. | `flp-file`, `FLParser`, `bravoh-daw` |

### 3.3 Variable-Length Integer (Varint) Mechanics

Variable-length payloads in FLP use a 7-bit little-endian variable-length quantity:

1. **Bit Layout:** Each byte carries 7 data bits (`byte & 0x7F`) and 1 continuation bit (`byte & 0x80`).
2. **Byte Order:** Little-endian groups. The first byte contains the least significant 7 bits (shift 0). If continuation bit 0x80 is set, the next byte contains the next 7 bits (shift 7), and so on.
3. **Termination:** Decoding terminates at the first byte where `(byte & 0x80) == 0`.
4. **Non-Canonical Encodings:** Some FL Studio writers emit non-canonical representations (e.g. 2-byte `\x85\x00` representing length 5). The StudioBridge codec records the exact length encoding bytes in `LenEnc` (`[FLP-01]`) to ensure 100% byte-identical re-serialization without canonicalization drift.

### 3.4 Text Encoding Decoupling (`[FLP-06]`)

Variable-length events encoding text (project title, comments, track names, plugin names) historically used ASCII or Windows-1252 codepages in early FL Studio versions, and UTF-16LE in modern releases.

The binary codec layer strictly treats all variable payloads as opaque `bytes`. Text decoding is explicitly decoupled and delegated to version-aware schema profiles (`v0.5.1`), ensuring the codec never corrupts raw bytes through premature string conversion.

---

## 4. Compliance & Verification Guarantees

- **AST Cleanliness:** No code from PyFLP or any GPL codebase was copied or consulted during authoring.
- **Byte Invariant Testing:** Verified by `tests/unit/flp/test_codec_roundtrip.py`, asserting `serialize(parse(b)) == b` across synthetic binaries and corpus files.
- **Performance Verification:** Bounded memory streaming reader (`iter_events`, `lazy=True`) tested against large projects (≥ 200 MB), maintaining memory bounds ≤ 3× file size and processing 50 MB projects in ≤ 3 seconds.
