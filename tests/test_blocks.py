"""Tests for fixed-size Dual6 block layouts."""

from __future__ import annotations

import random
import unittest

import dual6
from dual6 import (
    BLOCK40,
    BLOCK64,
    BLOCK128,
    Dual6Error,
    ErrorCode,
    get_layout,
    pack_block,
    pack_block128,
    pack_block40,
    pack_block64,
    unpack_block,
    unpack_block128,
    unpack_block40,
    unpack_block64,
)


class TestBlockLayouts(unittest.TestCase):
    def test_metadata(self) -> None:
        self.assertEqual((BLOCK64.symbols, BLOCK64.byte_length), (24, 8))
        self.assertEqual((BLOCK128.symbols, BLOCK128.byte_length), (48, 16))
        self.assertEqual((BLOCK40.symbols, BLOCK40.byte_length), (40, 13))

    def test_capacity_limits(self) -> None:
        self.assertTrue(6 ** 24 < (1 << 63))
        self.assertTrue(6 ** 48 < (1 << 125))
        self.assertTrue(6 ** 40 < (1 << 104))

    def test_information_density(self) -> None:
        self.assertAlmostEqual(BLOCK64.information_density, 0.96936, places=4)
        self.assertAlmostEqual(BLOCK128.information_density, 0.96936, places=4)
        self.assertAlmostEqual(BLOCK40.information_density, 0.99422, places=4)


class TestBlockRoundtrip(unittest.TestCase):
    def _roundtrip(self, layout) -> None:
        random.seed(10)
        for _ in range(200):
            symbols = [random.randrange(6) for _ in range(layout.symbols)]
            data = pack_block(symbols, layout)
            self.assertEqual(len(data), layout.byte_length)
            self.assertEqual(unpack_block(data, layout), symbols)

    def test_block64(self) -> None:
        self._roundtrip(BLOCK64)

    def test_block128(self) -> None:
        self._roundtrip(BLOCK128)

    def test_block40(self) -> None:
        self._roundtrip(BLOCK40)

    def test_extreme_values(self) -> None:
        for layout in (BLOCK64, BLOCK128, BLOCK40):
            for symbols in ([1] * layout.symbols, [5] * layout.symbols):
                data = pack_block(symbols, layout)
                self.assertEqual(unpack_block(data, layout), symbols)

    def test_wrappers(self) -> None:
        symbols = [1, 2, 3, 4, 5, 0] * 4
        self.assertEqual(unpack_block64(pack_block64(symbols)), symbols)
        symbols = [0, 1, 2, 3, 4, 5] * 8
        self.assertEqual(unpack_block128(pack_block128(symbols)), symbols)
        symbols = [5, 4, 3, 2, 1, 0, 1, 2] * 5
        self.assertEqual(unpack_block40(pack_block40(symbols)), symbols)


class TestBlockErrors(unittest.TestCase):
    def test_wrong_symbol_count(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_block([1, 1, 1], BLOCK64)
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)

    def test_wrong_byte_count(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_block(b"\x00" * 7, BLOCK64)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_invalid_symbol(self) -> None:
        symbols = [0] * BLOCK64.symbols
        symbols[0] = 6
        with self.assertRaises(Dual6Error) as ctx:
            pack_block(symbols, BLOCK64)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_DIGIT)

    def test_invalid_packing(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_block(b"\xff" * 8, BLOCK64)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_unknown_layout(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            get_layout("D6-999")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
