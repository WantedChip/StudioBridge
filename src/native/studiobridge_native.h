/**
 * StudioBridge Native Acceleration Helpers
 * Optional native C routines for high-throughput SysEx CRC calculation,
 * 7-bit septet packing, frame validation, and tolerance comparisons.
 *
 * Requirements:
 * - req: ARM-01: ARM64 and x64 dual-architecture native acceleration
 * - req: WIRE-02: SysEx wire frame layout and CRC-16/CCITT-FALSE
 */

#ifndef STUDIOBRIDGE_NATIVE_H
#define STUDIOBRIDGE_NATIVE_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32) || defined(__WIN32__)
    #define SB_EXPORT __declspec(dllexport)
#else
    #define SB_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Library metadata */
SB_EXPORT int sb_version(void);
SB_EXPORT const char* sb_build_arch(void);

/* CRC-16/CCITT-FALSE calculation */
SB_EXPORT uint16_t sb_crc16(const uint8_t* data, size_t len, uint16_t init);
SB_EXPORT uint16_t sb_crc16_bitwise(const uint8_t* data, size_t len, uint16_t init);

/* CRC-32 (IEEE 802.3) calculation */
SB_EXPORT uint32_t sb_crc32(const uint8_t* data, size_t len, uint32_t init);

/* 7-bit MIDI Septet packing and unpacking */
SB_EXPORT int sb_pack_crc(uint16_t crc, uint8_t* out_septets);
SB_EXPORT int sb_unpack_crc(const uint8_t* septets, uint16_t* out_crc);

SB_EXPORT int sb_pack_septets_14(uint16_t val, uint8_t* out_septets);
SB_EXPORT int sb_unpack_septets_14(uint8_t b0, uint8_t b1, uint16_t* out_val);

SB_EXPORT int sb_pack_septets_21(uint32_t val, uint8_t* out_septets);
SB_EXPORT int sb_unpack_septets_21(uint8_t b0, uint8_t b1, uint8_t b2, uint32_t* out_val);

/* SysEx Frame validation and verification */
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
);

/* Numeric tolerance comparison */
SB_EXPORT int sb_tolerance_matches(double expected, double actual, double tol);

#ifdef __cplusplus
}
#endif

#endif /* STUDIOBRIDGE_NATIVE_H */
