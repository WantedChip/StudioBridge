/**
 * StudioBridge Native Acceleration Helpers Implementation
 *
 * Implements CRC-16/CCITT-FALSE, CRC-32 (IEEE 802.3), 7-bit MIDI septet packing,
 * frame validation, and floating-point tolerance comparisons.
 *
 * Requirements:
 * - req: ARM-01: Native toolchain dual compilation and parity
 * - req: WIRE-02: SysEx wire frame layout and CRC-16/CCITT-FALSE
 */

#include "studiobridge_native.h"
#include <math.h>
#include <stdbool.h>
#include <string.h>

#define CRC16_POLY 0x1021U
#define CRC16_INIT 0xFFFFU

#define SYSEX_START 0xF0
#define SYSEX_END 0xF7
#define MANUFACTURER_ID 0x7D
#define PROTOCOL_VERSION 0x01
#define FRAME_OVERHEAD 22

/* 256-entry lookup table for CRC-16/CCITT-FALSE (poly 0x1021, MSB-first) */
static uint16_t s_crc16_table[256];
static bool s_crc16_table_initialized = false;

/* 256-entry lookup table for CRC-32 (IEEE 802.3, poly 0xEDB88320, LSB-first) */
static uint32_t s_crc32_table[256];
static bool s_crc32_table_initialized = false;

static void init_crc16_table(void) {
    if (s_crc16_table_initialized) {
        return;
    }
    for (uint32_t byte = 0; byte < 256; ++byte) {
        uint32_t curr = byte << 8;
        for (int bit = 0; bit < 8; ++bit) {
            if (curr & 0x8000U) {
                curr = ((curr << 1) ^ CRC16_POLY) & 0xFFFFU;
            } else {
                curr = (curr << 1) & 0xFFFFU;
            }
        }
        s_crc16_table[byte] = (uint16_t)curr;
    }
    s_crc16_table_initialized = true;
}

static void init_crc32_table(void) {
    if (s_crc32_table_initialized) {
        return;
    }
    for (uint32_t byte = 0; byte < 256; ++byte) {
        uint32_t c = byte;
        for (int bit = 0; bit < 8; ++bit) {
            if (c & 1) {
                c = 0xEDB88320U ^ (c >> 1);
            } else {
                c = c >> 1;
            }
        }
        s_crc32_table[byte] = c;
    }
    s_crc32_table_initialized = true;
}

SB_EXPORT int sb_version(void) {
    return 1;
}

SB_EXPORT const char* sb_build_arch(void) {
#if defined(_M_ARM64) || defined(__aarch64__)
    return "ARM64";
#elif defined(_M_X64) || defined(__x86_64__)
    return "x64";
#else
    return "unknown";
#endif
}

SB_EXPORT uint16_t sb_crc16(const uint8_t* data, size_t len, uint16_t init) {
    if (!s_crc16_table_initialized) {
        init_crc16_table();
    }
    uint16_t crc = init;
    for (size_t i = 0; i < len; ++i) {
        uint8_t index = (uint8_t)((crc >> 8) ^ data[i]);
        crc = (uint16_t)(((crc << 8) & 0xFFFFU) ^ s_crc16_table[index]);
    }
    return crc & 0xFFFFU;
}

SB_EXPORT uint16_t sb_crc16_bitwise(const uint8_t* data, size_t len, uint16_t init) {
    uint16_t crc = init & 0xFFFFU;
    for (size_t i = 0; i < len; ++i) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (int bit = 0; bit < 8; ++bit) {
            if (crc & 0x8000U) {
                crc = (uint16_t)(((crc << 1) ^ CRC16_POLY) & 0xFFFFU);
            } else {
                crc = (uint16_t)((crc << 1) & 0xFFFFU);
            }
        }
    }
    return crc & 0xFFFFU;
}

SB_EXPORT uint32_t sb_crc32(const uint8_t* data, size_t len, uint32_t init) {
    if (!s_crc32_table_initialized) {
        init_crc32_table();
    }
    uint32_t c = ~init;
    for (size_t i = 0; i < len; ++i) {
        c = s_crc32_table[(c ^ data[i]) & 0xFFU] ^ (c >> 8);
    }
    return ~c;
}

SB_EXPORT int sb_pack_crc(uint16_t crc, uint8_t* out_septets) {
    if (!out_septets) {
        return -1;
    }
    out_septets[0] = (uint8_t)((crc >> 14) & 0x03U);
    out_septets[1] = (uint8_t)((crc >> 7) & 0x7FU);
    out_septets[2] = (uint8_t)(crc & 0x7FU);
    return 0;
}

SB_EXPORT int sb_unpack_crc(const uint8_t* septets, uint16_t* out_crc) {
    if (!septets || !out_crc) {
        return -1;
    }
    uint8_t b0 = septets[0];
    uint8_t b1 = septets[1];
    uint8_t b2 = septets[2];
    if (b0 > 0x03U || b1 > 0x7FU || b2 > 0x7FU) {
        return -1;
    }
    *out_crc = (uint16_t)(((b0 & 0x03U) << 14) | ((b1 & 0x7FU) << 7) | (b2 & 0x7FU));
    return 0;
}

SB_EXPORT int sb_pack_septets_14(uint16_t val, uint8_t* out_septets) {
    if (!out_septets || val > 0x3FFFU) {
        return -1;
    }
    out_septets[0] = (uint8_t)((val >> 7) & 0x7FU);
    out_septets[1] = (uint8_t)(val & 0x7FU);
    return 0;
}

SB_EXPORT int sb_unpack_septets_14(uint8_t b0, uint8_t b1, uint16_t* out_val) {
    if (!out_val || b0 > 0x7FU || b1 > 0x7FU) {
        return -1;
    }
    *out_val = (uint16_t)(((b0 & 0x7FU) << 7) | (b1 & 0x7FU));
    return 0;
}

SB_EXPORT int sb_pack_septets_21(uint32_t val, uint8_t* out_septets) {
    if (!out_septets || val > 0x1FFFFFU) {
        return -1;
    }
    out_septets[0] = (uint8_t)((val >> 14) & 0x7FU);
    out_septets[1] = (uint8_t)((val >> 7) & 0x7FU);
    out_septets[2] = (uint8_t)(val & 0x7FU);
    return 0;
}

SB_EXPORT int sb_unpack_septets_21(uint8_t b0, uint8_t b1, uint8_t b2, uint32_t* out_val) {
    if (!out_val || b0 > 0x7FU || b1 > 0x7FU || b2 > 0x7FU) {
        return -1;
    }
    *out_val = ((uint32_t)(b0 & 0x7FU) << 14) | ((uint32_t)(b1 & 0x7FU) << 7) | (uint32_t)(b2 & 0x7FU);
    return 0;
}

SB_EXPORT int sb_validate_frame(
    const uint8_t* raw,
    size_t len,
    uint8_t* out_kind,
    uint8_t* out_flags,
    uint16_t* out_sid,
    uint32_t* out_mid,
    uint16_t* out_cidx,
    uint16_t* out_ccnt,
    uint16_t* out_plen,
    uint16_t* out_crc
) {
    if (!raw || len < FRAME_OVERHEAD) {
        return -1; /* Too short */
    }
    if (raw[0] != SYSEX_START || raw[len - 1] != SYSEX_END) {
        return -2; /* Framing byte mismatch */
    }
    if (raw[1] != MANUFACTURER_ID || raw[2] != 'S' || raw[3] != 'B') {
        return -3; /* Manufacturer or magic identifier mismatch */
    }
    if (raw[4] != PROTOCOL_VERSION) {
        return -4; /* Protocol version mismatch */
    }

    uint8_t kind = raw[5];
    uint8_t flags = raw[6];

    uint16_t sid = 0;
    if (sb_unpack_septets_14(raw[7], raw[8], &sid) != 0) {
        return -7;
    }

    uint32_t mid = 0;
    if (sb_unpack_septets_21(raw[9], raw[10], raw[11], &mid) != 0) {
        return -7;
    }

    uint16_t cidx = 0;
    if (sb_unpack_septets_14(raw[12], raw[13], &cidx) != 0) {
        return -7;
    }

    uint16_t ccnt = 0;
    if (sb_unpack_septets_14(raw[14], raw[15], &ccnt) != 0) {
        return -7;
    }

    uint16_t plen = 0;
    if (sb_unpack_septets_14(raw[16], raw[17], &plen) != 0) {
        return -7;
    }

    /* Verify payload length matches total frame length */
    if (len != (size_t)(FRAME_OVERHEAD + plen)) {
        return -5; /* Length mismatch */
    }

    /* Compute CRC over [VER ... last payload byte]: raw[4] to raw[17 + plen] */
    size_t crc_span = 14 + plen;
    uint16_t computed_crc = sb_crc16(&raw[4], crc_span, CRC16_INIT);

    /* Unpack expected CRC from raw[18 + plen ... 20 + plen] */
    uint16_t expected_crc = 0;
    if (sb_unpack_crc(&raw[18 + plen], &expected_crc) != 0) {
        return -7;
    }

    if (computed_crc != expected_crc) {
        return -6; /* CRC error */
    }

    if (out_kind) *out_kind = kind;
    if (out_flags) *out_flags = flags;
    if (out_sid) *out_sid = sid;
    if (out_mid) *out_mid = mid;
    if (out_cidx) *out_cidx = cidx;
    if (out_ccnt) *out_ccnt = ccnt;
    if (out_plen) *out_plen = plen;
    if (out_crc) *out_crc = expected_crc;

    return 0;
}

SB_EXPORT int sb_tolerance_matches(double expected, double actual, double tol) {
    if (isnan(expected) || isnan(actual) || isnan(tol)) {
        return 0;
    }
    if (isinf(expected) || isinf(actual)) {
        return (expected == actual) ? 1 : 0;
    }
    double diff = fabs(actual - expected);
    return (diff <= tol) ? 1 : 0;
}
