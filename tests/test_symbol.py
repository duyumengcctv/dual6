"""Tests for the single-symbol codec."""

from __future__ import annotations

import unittest
from itertools import product

from dual6 import Dual6Error, ErrorCode, decode_digit, encode_digit


class TestSymbolCodec(unittest.TestCase):
    def test_all_six_roundtrips(self) -> None:
        for bit, trit in product((0, 1), (-1, 0, 1)):
            d = encode_digit(bit, trit)
            self.assertIn(d, range(6))
            self.assertEqual(decode_digit(d), (bit, trit))

    def test_decode_table(self) -> None:
        expected = [(0, -1), (0, 0), (0, +1), (1, -1), (1, 0), (1, +1)]
        self.assertEqual([decode_digit(d) for d in range(6)], expected)

    def test_invalid_inputs(self) -> None:
        for bad_bit in (-1, 2, 9):
            with self.assertRaises(Dual6Error) as ctx:
                encode_digit(bad_bit, 0)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)

        for bad_trit in (-2, 2, 9):
            with self.assertRaises(Dual6Error) as ctx:
                encode_digit(0, bad_trit)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_TRIT)

        for bad_digit in (-1, 6, 99):
            with self.assertRaises(Dual6Error) as ctx:
                decode_digit(bad_digit)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_DIGIT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
