"""Tests for binary/ternary stream adapters."""

from __future__ import annotations

import unittest

from dual6 import Dual6Error, ErrorCode
from dual6.adapters import (
    bits_to_dual6_block64,
    bits_to_symbols,
    dual6_block64_to_bits,
    dual6_block64_to_trits,
    symbols_to_bits,
    symbols_to_trits,
    trits_to_dual6_block64,
    trits_to_symbols,
)


class TestTernaryAdapter(unittest.TestCase):
    def test_trits_symbols_roundtrip(self) -> None:
        trits = [1, -1, 0, 0, 1, -1]
        symbols = trits_to_symbols(trits, fill_bit=0)
        self.assertEqual(symbols_to_trits(symbols), trits)

    def test_fill_bit(self) -> None:
        trits = [1, -1]
        symbols = trits_to_symbols(trits, fill_bit=1)
        bits, got = symbols_to_bits(symbols), symbols_to_trits(symbols)
        self.assertEqual(bits, [1, 1])
        self.assertEqual(got, trits)

    def test_block64_roundtrip(self) -> None:
        trits = [1, -1, 0] * 8
        data = trits_to_dual6_block64(trits, fill_bit=0)
        self.assertEqual(len(data), 8)
        self.assertEqual(dual6_block64_to_trits(data), trits)

    def test_invalid_trit(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            trits_to_symbols([0, 2, 0])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_TRIT)

    def test_invalid_fill_bit(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            trits_to_symbols([0], fill_bit=2)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)

    def test_block_width(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            trits_to_dual6_block64([0] * 23)
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)


class TestBinaryAdapter(unittest.TestCase):
    def test_bits_symbols_roundtrip(self) -> None:
        bits = [1, 0, 1, 0, 0, 1]
        symbols = bits_to_symbols(bits, fill_trit=0)
        self.assertEqual(symbols_to_bits(symbols), bits)

    def test_fill_trit(self) -> None:
        bits = [1, 0]
        symbols = bits_to_symbols(bits, fill_trit=-1)
        self.assertEqual(symbols_to_bits(symbols), bits)
        self.assertEqual(symbols_to_trits(symbols), [-1, -1])

    def test_block64_roundtrip(self) -> None:
        bits = [1, 0] * 12
        data = bits_to_dual6_block64(bits, fill_trit=0)
        self.assertEqual(len(data), 8)
        self.assertEqual(dual6_block64_to_bits(data), bits)

    def test_invalid_bit(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            bits_to_symbols([0, 2, 0])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)

    def test_invalid_fill_trit(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            bits_to_symbols([0], fill_trit=2)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_TRIT)

    def test_block_width(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            bits_to_dual6_block64([0] * 23)
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
