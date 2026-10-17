#ifndef DUAL6_H
#define DUAL6_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Status codes (negative return values). */
#define DUAL6_ERR_INVALID_ARG      (-1)
#define DUAL6_ERR_WIDTH_MISMATCH   (-2)
#define DUAL6_ERR_INVALID_LAYOUT   (-3)
#define DUAL6_ERR_BUFFER_TOO_SMALL (-4)

/* Returns encoded digit 0..5 on success, negative status on invalid input. */
int32_t dual6_encode_digit(uint8_t bit, int8_t trit);

/* Writes bit and trit, returns 0 on success and negative status on error. */
int32_t dual6_decode_digit(uint8_t digit, uint8_t *out_bit, int8_t *out_trit);

/*
 * Batch pack: input is a flat symbol stream (n_symbols must be a multiple of
 * 24).  Writes 8 * n_symbols / 24 bytes to `out`.
 *
 * Returns bytes written on success, or a negative status.
 */
int32_t dual6_pack_block64_many(const uint8_t *symbols, size_t n_symbols,
                                uint8_t *out, size_t out_capacity);

/*
 * Batch unpack: input is a flat D6-64 byte stream (n_bytes must be a multiple
 * of 8).  Writes 24 * n_bytes / 8 symbols to `out`.
 *
 * Returns symbols written on success, or a negative status.
 */
int32_t dual6_unpack_block64_many(const uint8_t *data, size_t n_bytes,
                                  uint8_t *out, size_t out_capacity);

#ifdef __cplusplus
}
#endif

#endif /* DUAL6_H */
