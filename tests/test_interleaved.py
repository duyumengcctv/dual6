"""Tests for interleaved base-6 packing."""

from __future__ import annotations

import random
import unittest
from itertools import product

from dual6 import (
    Dual6Error,
    ErrorCode,
    fits_unsigned_word,
    max_interleaved,
    pack_digits,
    unpack_digits,
)


class TestInterleaved(unittest.TestCase):
    def test_all_five_symbol_roundtrips(self) -> None:
        for symbols in product(range(6), repeat=5):
            value = pack_digits(symbols)
            self.assertLess(value, 1 << 13)
            self.assertEqual(tuple(unpack_digits(value, 5)), symbols)

    def test_all_13bit_values_in_valid_range(self) -> None:
        for value in range(6 ** 5):
            symbols = unpack_digits(value, 5)
            self.assertEqual(pack_digits(symbols), value)

    def test_random_widths(self) -> None:
        random.seed(1)
        for width in range(0, 25):
            for _ in range(20):
                symbols = [random.randrange(6) for _ in range(width)]
                value = pack_digits(symbols)
                self.assertEqual(unpack_digits(value, width), symbols)

    def test_invalid_packing(self) -> None:
        for value, width in ((6 ** 5, 5), (-1, 5), (1, 0)):
            with self.assertRaises(Dual6Error) as ctx:
                unpack_digits(value, width)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_invalid_symbol(self) -> None:
        for bad in (-1, 6, 99):
            with self.assertRaises(Dual6Error) as ctx:
                pack_digits([0, bad, 0])
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_DIGIT)

    def test_max_interleaved(self) -> None:
        self.assertEqual(max_interleaved(0), 0)
        self.assertEqual(max_interleaved(5), 7775)
        self.assertEqual(max_interleaved(24), 6 ** 24 - 1)

    def test_64bit_capacity(self) -> None:
        self.assertTrue(fits_unsigned_word(24, 63))
        self.assertTrue(fits_unsigned_word(24, 64))
        self.assertFalse(fits_unsigned_word(25, 64))

    def test_fits_unsigned_word_rejects_negative(self) -> None:
        for width, word_bits in ((-1, 8), (4, -1), (-1, -1)):
            with self.assertRaises(Dual6Error) as ctx:
                fits_unsigned_word(width, word_bits)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_fits_unsigned_word_matches_exact_value(self) -> None:
        for width in range(0, 60):
            for word_bits in range(0, 160):
                self.assertEqual(
                    fits_unsigned_word(width, word_bits),
                    6 ** width <= (1 << word_bits),
                    f"width={width} word_bits={word_bits}",
                )

    def test_fits_unsigned_word_pathological_width_is_cheap(self) -> None:
        # Regression: a huge width used to materialise 6 ** width and hang.
        self.assertFalse(fits_unsigned_word(10 ** 12, 64))
        # Above the exact comparison cutoff the log2 path still agrees.
        self.assertTrue(fits_unsigned_word(5000, 13000))
        self.assertFalse(fits_unsigned_word(5000, 12900))

    def test_large_width_falls_back_to_ref(self) -> None:
        # The Rust u128 helper only supports <= 48 symbols; the package must
        # transparently fall back to the pure-Python path beyond that.
        for width in (48, 49, 100):
            symbols = [(i * 7) % 6 for i in range(width)]
            value = pack_digits(symbols)
            self.assertEqual(unpack_digits(value, width), symbols)
            self.assertEqual(max_interleaved(width), 6 ** width - 1)
        self.assertTrue(fits_unsigned_word(100, 512))
        self.assertFalse(fits_unsigned_word(100, 256))



if __name__ == "__main__":
    unittest.main(verbosity=2)
