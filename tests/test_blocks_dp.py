"""Tests for dual-plane fixed blocks."""

from __future__ import annotations

import random
import unittest

from dual6 import (
    BLOCK40_DP,
    BLOCK64_DP,
    BLOCK128_DP,
    Dual6Error,
    ErrorCode,
    get_dp_layout,
    pack_bits_bytes,
    pack_block128_dp,
    pack_block40_dp,
    pack_block64_dp,
    pack_block_dp,
    pack_trits_bytes,
    unpack_block128_dp,
    unpack_block40_dp,
    unpack_block64_dp,
    unpack_block_dp,
)


class TestDualPlaneBlockLayouts(unittest.TestCase):
    def test_metadata(self) -> None:
        self.assertEqual((BLOCK64_DP.symbols, BLOCK64_DP.byte_length), (24, 8))
        self.assertEqual((BLOCK64_DP.bit_bytes, BLOCK64_DP.trit_bytes), (3, 5))
        self.assertEqual((BLOCK128_DP.symbols, BLOCK128_DP.byte_length), (48, 16))
        self.assertEqual((BLOCK128_DP.bit_bytes, BLOCK128_DP.trit_bytes), (6, 10))
        self.assertEqual((BLOCK40_DP.symbols, BLOCK40_DP.byte_length), (40, 13))
        self.assertEqual((BLOCK40_DP.bit_bytes, BLOCK40_DP.trit_bytes), (5, 8))

    def test_exact_fit(self) -> None:
        for layout in (BLOCK64_DP, BLOCK128_DP, BLOCK40_DP):
            self.assertEqual(layout.bit_bytes + layout.trit_bytes, layout.byte_length)
            self.assertEqual(layout.bit_bytes, (layout.symbols + 7) // 8)
            self.assertEqual(layout.trit_bytes, (layout.symbols + 4) // 5)


class TestDualPlaneBlockRoundtrip(unittest.TestCase):
    def _roundtrip(self, layout) -> None:
        random.seed(20)
        for _ in range(200):
            bits = [random.randrange(2) for _ in range(layout.symbols)]
            trits = [random.choice((-1, 0, 1)) for _ in range(layout.symbols)]
            data = pack_block_dp(bits, trits, layout)
            self.assertEqual(len(data), layout.byte_length)
            self.assertEqual(unpack_block_dp(data, layout), (bits, trits))

    def test_block64_dp(self) -> None:
        self._roundtrip(BLOCK64_DP)

    def test_block128_dp(self) -> None:
        self._roundtrip(BLOCK128_DP)

    def test_block40_dp(self) -> None:
        self._roundtrip(BLOCK40_DP)

    def test_plane_split(self) -> None:
        bits = [1, 0, 1, 0, 1, 0] * 4
        trits = [1, -1, 0, 0, 1, -1] * 4
        data = pack_block64_dp(bits, trits)
        self.assertEqual(data[:3], pack_bits_bytes(bits))
        self.assertEqual(data[3:], pack_trits_bytes(trits))

    def test_wrappers(self) -> None:
        bits = [1, 0] * 12
        trits = [1, -1] * 12
        self.assertEqual(unpack_block64_dp(pack_block64_dp(bits, trits)), (bits, trits))

        bits = [0, 1] * 24
        trits = [0, 1] * 24
        self.assertEqual(unpack_block128_dp(pack_block128_dp(bits, trits)), (bits, trits))

        bits = [1, 0, 1, 0, 1] * 8
        trits = [1, 0, -1, 0, 1] * 8
        self.assertEqual(unpack_block40_dp(pack_block40_dp(bits, trits)), (bits, trits))


class TestDualPlaneBlockErrors(unittest.TestCase):
    def test_wrong_width(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_block_dp([0, 1], [0, 1], BLOCK64_DP)
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)

    def test_wrong_byte_count(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_block_dp(b"\x00" * 7, BLOCK64_DP)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_invalid_bit(self) -> None:
        bits = [0] * BLOCK64_DP.symbols
        trits = [0] * BLOCK64_DP.symbols
        bits[0] = 2
        with self.assertRaises(Dual6Error) as ctx:
            pack_block_dp(bits, trits, BLOCK64_DP)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)

    def test_invalid_trit(self) -> None:
        bits = [0] * BLOCK64_DP.symbols
        trits = [0] * BLOCK64_DP.symbols
        trits[0] = 2
        with self.assertRaises(Dual6Error) as ctx:
            pack_block_dp(bits, trits, BLOCK64_DP)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_TRIT)

    def test_unknown_layout(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            get_dp_layout("D6-999-DP")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
