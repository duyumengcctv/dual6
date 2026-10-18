"""Scalar type / range validation is part of the public contract.

The native backend converts Python objects to Rust integers before the core
function runs, so bad values can fail in PyO3 rather than in the core.  These
tests pin the resulting ``Dual6Error`` codes so the reference and native
backends stay interchangeable.
"""

from __future__ import annotations

import unittest

import dual6
from dual6 import Dual6Error, ErrorCode


class ValidationMixin:
    def assertCode(self, code, fn, *args):
        with self.assertRaises(Dual6Error) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.code, code, f"{fn.__name__}{args!r}")


class TestBitValidation(ValidationMixin, unittest.TestCase):
    def test_non_integer_bits_are_rejected(self):
        self.assertCode(ErrorCode.INVALID_BIT, dual6.pack_bits_bytes, [0.0] * 8)
        self.assertCode(ErrorCode.INVALID_BIT, dual6.mux, [1.0], [0])
        self.assertCode(ErrorCode.INVALID_BIT, dual6.encode_digit, 1.0, 0)

    def test_out_of_range_bits_keep_the_specific_code(self):
        self.assertCode(ErrorCode.INVALID_BIT, dual6.mux, [300], [0])
        self.assertCode(ErrorCode.INVALID_BIT, dual6.pack_bits_bytes, [300])
        self.assertCode(ErrorCode.INVALID_BIT, dual6.encode_digit, 300, 0)

    def test_bool_is_treated_as_an_int(self):
        self.assertEqual(dual6.pack_bits_bytes([True] * 8), b"\xff")
        self.assertEqual(dual6.mux([True], [0]), [4])


class TestTritValidation(ValidationMixin, unittest.TestCase):
    def test_non_integer_trits_are_rejected(self):
        self.assertCode(ErrorCode.INVALID_TRIT, dual6.pack_trits_bytes, [1.0] * 5)
        self.assertCode(ErrorCode.INVALID_TRIT, dual6.mux, [0], [-1.0])
        self.assertCode(ErrorCode.INVALID_TRIT, dual6.encode_digit, 0, 1.0)

    def test_out_of_range_trits_keep_the_specific_code(self):
        self.assertCode(ErrorCode.INVALID_TRIT, dual6.mux, [0], [-300])
        self.assertCode(ErrorCode.INVALID_TRIT, dual6.encode_digit, 0, 300)
        self.assertCode(ErrorCode.INVALID_TRIT, dual6.pack_trits_bytes, [300])


class TestSymbolValidation(ValidationMixin, unittest.TestCase):
    def test_non_integer_symbols_are_rejected(self):
        self.assertCode(ErrorCode.INVALID_DIGIT, dual6.decode_digit, 1.0)
        self.assertCode(ErrorCode.INVALID_DIGIT, dual6.demux, [1.0])
        self.assertCode(ErrorCode.INVALID_DIGIT, dual6.pack_block64, [0.0] * 24)

    def test_out_of_range_symbols_keep_the_specific_code(self):
        self.assertCode(ErrorCode.INVALID_DIGIT, dual6.decode_digit, 300)
        self.assertCode(ErrorCode.INVALID_DIGIT, dual6.demux, [300])
        self.assertCode(ErrorCode.INVALID_DIGIT, dual6.pack_block64, [300] * 24)

    def test_bool_is_treated_as_an_int(self):
        self.assertEqual(dual6.decode_digit(True), (0, 0))
        self.assertEqual(dual6.pack_digits([True]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
