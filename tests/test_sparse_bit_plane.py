"""R2 · block-compacted ("sparse") bit plane, layout id 1.

When the bit channel is a mask that is a few percent dense, a fixed 1.0 bpw
plane spends almost all of its bytes storing zeros.  Layout 1 stores a 1-bit
flag per block plus the bitmap only for blocks that actually contain a set bit;
the trit plane stays contiguous so a ternary engine reads the same bytes.
"""

from __future__ import annotations

import random
import unittest

import dual6
from dual6 import Dual6Error, ErrorCode

HEADER = 33


def sparse_layout() -> int:
    return dual6.LAYOUT_DUAL_PLANE_SPARSE


class SparseBitPlane(unittest.TestCase):
    def test_layout_id_is_stable(self) -> None:
        self.assertEqual(sparse_layout(), 1)

    def test_roundtrip_mixed_density(self) -> None:
        rng = random.Random(11)
        for density in (0.0, 0.02, 0.1, 0.5, 1.0):
            for block in (24, 48):
                width = block * 10
                bits = [1 if rng.random() < density else 0 for _ in range(width)]
                trits = [rng.randrange(-1, 2) for _ in range(width)]
                with self.subTest(density=density, block=block):
                    frame = dual6.pack_dual_plane_v2(
                        bits, trits, block_symbols=block, layout=sparse_layout()
                    )
                    got_bits, got_trits, meta = dual6.unpack_dual_plane_v2(frame)
                    self.assertEqual(got_bits, bits)
                    self.assertEqual(got_trits, trits)
                    self.assertEqual(meta["layout"], sparse_layout())
                    self.assertEqual(meta["block_count"] * block, width)
                    self.assertEqual(meta["block_bytes"], (block + 4) // 5)

    def test_all_zero_mask_costs_only_flags_and_trits(self) -> None:
        width, block = 240, 24
        blocks = width // block
        frame = dual6.pack_dual_plane_v2(
            [0] * width, [1] * width, block_symbols=block, layout=sparse_layout()
        )
        flag_bytes = (blocks + 7) // 8
        trit_bytes = blocks * ((block + 4) // 5)
        self.assertEqual(len(frame) - HEADER, flag_bytes + trit_bytes)

    def test_sparse_is_smaller_than_dense_when_mask_is_sparse(self) -> None:
        rng = random.Random(5)
        width, block = 480, 24
        bits = [1 if rng.random() < 0.01 else 0 for _ in range(width)]
        trits = [0] * width
        dense = dual6.pack_dual_plane_v2(bits, trits, block_symbols=block)
        lean = dual6.pack_dual_plane_v2(
            bits, trits, block_symbols=block, layout=sparse_layout()
        )
        self.assertLess(len(lean), len(dense) * 0.85)

    def test_dense_mask_is_not_helped(self) -> None:
        # honesty check: at high density the flags are pure overhead
        rng = random.Random(6)
        width, block = 480, 24
        bits = [rng.randrange(2) for _ in range(width)]
        trits = [0] * width
        dense = dual6.pack_dual_plane_v2(bits, trits, block_symbols=block)
        lean = dual6.pack_dual_plane_v2(
            bits, trits, block_symbols=block, layout=sparse_layout()
        )
        self.assertGreater(len(lean), len(dense))

    def test_requires_blocks(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            dual6.pack_dual_plane_v2([0] * 8, [0] * 8, layout=sparse_layout())
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_unknown_layout_is_rejected(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            dual6.pack_dual_plane_v2([0] * 24, [0] * 24, block_symbols=24, layout=7)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_corrupted_payload_is_rejected(self) -> None:
        rng = random.Random(8)
        width, block = 240, 24
        bits = [1 if rng.random() < 0.05 else 0 for _ in range(width)]
        trits = [rng.randrange(-1, 2) for _ in range(width)]
        frame = bytearray(
            dual6.pack_dual_plane_v2(bits, trits, block_symbols=block, layout=sparse_layout())
        )
        frame[-1] ^= 0xFF          # break a trit byte -> CRC must catch it
        with self.assertRaises(Dual6Error) as ctx:
            dual6.unpack_dual_plane_v2(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.CRC_MISMATCH)

    def test_trit_plane_stays_contiguous_and_unchanged(self) -> None:
        rng = random.Random(9)
        width, block = 240, 24
        bits = [1 if i % 20 == 0 else 0 for i in range(width)]
        trits = [rng.randrange(-1, 2) for _ in range(width)]
        frame = dual6.pack_dual_plane_v2(
            bits, trits, block_symbols=block, layout=sparse_layout()
        )
        payload = frame[HEADER:]
        trit_area = payload[-(width // block) * ((block + 4) // 5):]
        expected = b"".join(
            bytes(dual6.pack_trits_bytes(trits[i : i + block]))
            for i in range(0, width, block)
        )
        self.assertEqual(trit_area, expected)

    def test_frame_auto_detects_the_layout(self) -> None:
        width, block = 48, 24
        bits = [1] + [0] * (width - 1)
        trits = [1] * width
        frame = dual6.pack_dual_plane_v2(bits, trits, block_symbols=block, layout=sparse_layout())
        version, got_bits, got_trits, meta = dual6.unpack_frame_auto(frame)
        self.assertEqual(version, 2)
        self.assertEqual(got_bits, bits)
        self.assertEqual(got_trits, trits)
        self.assertEqual(meta["layout"], sparse_layout())


if __name__ == "__main__":
    unittest.main(verbosity=2)
