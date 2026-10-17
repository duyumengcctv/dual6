"""Consolidated property tests for the Dual6 tool surface."""

from __future__ import annotations

import random
import unittest

from dual6 import (
    BLOCK40,
    BLOCK64,
    BLOCK128,
    BLOCK40_DP,
    BLOCK64_DP,
    BLOCK128_DP,
    pack_bits_into,
    pack_block,
    pack_block_dp,
    pack_dual_plane_into,
    pack_dual_plane,
    pack_dual_plane_v1,
    pack_dual_plane_v2,
    pack_trits_into,
    unpack_bits_from,
    unpack_block,
    unpack_block_dp,
    unpack_dual_plane,
    unpack_dual_plane_from,
    unpack_dual_plane_v1,
    unpack_dual_plane_v2,
    unpack_trits_from,
)


class TestProperties(unittest.TestCase):
    def test_all_interleaved_blocks(self) -> None:
        rng = random.Random(41)
        for layout in (BLOCK64, BLOCK128, BLOCK40):
            for _ in range(20):
                symbols = [rng.randrange(6) for _ in range(layout.symbols)]
                data = pack_block(symbols, layout)
                self.assertEqual(unpack_block(data, layout), symbols)

    def test_all_dual_plane_blocks(self) -> None:
        rng = random.Random(42)
        for layout in (BLOCK64_DP, BLOCK128_DP, BLOCK40_DP):
            for _ in range(20):
                bits = [rng.randrange(2) for _ in range(layout.symbols)]
                trits = [rng.choice((-1, 0, 1)) for _ in range(layout.symbols)]
                data = pack_block_dp(bits, trits, layout)
                self.assertEqual(unpack_block_dp(data, layout), (bits, trits))

    def test_all_frames(self) -> None:
        rng = random.Random(43)
        for _ in range(40):
            width = rng.randrange(0, 65)
            bits = [rng.randrange(2) for _ in range(width)]
            trits = [rng.choice((-1, 0, 1)) for _ in range(width)]
            cases = (
                (pack_dual_plane, unpack_dual_plane),
                (pack_dual_plane_v1, unpack_dual_plane_v1),
            )
            for pack, unpack in cases:
                frame = pack(bits, trits)
                self.assertEqual(unpack(frame), (bits, trits))
            frame = pack_dual_plane_v2(bits, trits)
            got_bits, got_trits, _ = unpack_dual_plane_v2(frame)
            self.assertEqual((got_bits, got_trits), (bits, trits))

    def test_buffer_roundtrips(self) -> None:
        rng = random.Random(44)
        for width in range(0, 65):
            bits = [rng.randrange(2) for _ in range(width)]
            trits = [rng.choice((-1, 0, 1)) for _ in range(width)]
            buffer = bytearray(256)
            offset = rng.randrange(0, 8)
            pack_bits_into(bits, buffer, offset)
            self.assertEqual(unpack_bits_from(buffer, width, offset), bits)
            pack_trits_into(trits, buffer, offset)
            self.assertEqual(unpack_trits_from(buffer, width, offset), trits)
            pack_dual_plane_into(bits, trits, buffer, offset)
            self.assertEqual(unpack_dual_plane_from(buffer, width, offset), (bits, trits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
