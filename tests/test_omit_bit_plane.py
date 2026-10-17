"""R1 · trit-only D6P2 frames (`FLAG_OMIT_BIT_PLANE`).

A pure-ternary payload used to pay for a bit plane full of zeros: 2.6 bpw
instead of 1.6.  The flag removes that plane, which is the difference between
losing to TQ1_0 on storage and matching it.
"""

from __future__ import annotations

import random
import unittest

import dual6
from dual6 import Dual6Error, ErrorCode

FLAG = dual6.FLAG_OMIT_BIT_PLANE
HEADER = 33


class OmitBitPlane(unittest.TestCase):
    def test_flag_value_is_stable(self) -> None:
        self.assertEqual(FLAG, 0x0001)

    def test_payload_shrinks_by_exactly_the_bit_plane(self) -> None:
        for width in (0, 1, 8, 24, 40, 48, 129):
            bits = [0] * width
            trits = [1] * width
            with self.subTest(width=width):
                full = dual6.pack_dual_plane_v2(bits, trits)
                lean = dual6.pack_dual_plane_v2(bits, trits, flags=FLAG)
                saved = len(full) - len(lean)
                self.assertEqual(saved, (width + 7) // 8)
                self.assertEqual(len(lean) - HEADER, (width + 4) // 5)

    def test_pure_ternary_reaches_tq1_density(self) -> None:
        width = 65536
        frame = dual6.pack_dual_plane_v2([0] * width, [1] * width, flags=FLAG)
        bpw = len(frame) * 8 / width
        self.assertLess(bpw, 1.7, f"expected ~1.6 bpw, got {bpw:.3f}")

    def test_roundtrip_returns_zero_bits(self) -> None:
        rng = random.Random(5)
        for width in (0, 1, 7, 24, 40, 48, 96):
            trits = [rng.randrange(-1, 2) for _ in range(width)]
            frame = dual6.pack_dual_plane_v2([0] * width, trits, flags=FLAG)
            bits, got, meta = dual6.unpack_dual_plane_v2(frame)
            with self.subTest(width=width):
                self.assertEqual(got, trits)
                self.assertEqual(bits, [0] * width)
                self.assertEqual(meta["flags"] & FLAG, FLAG)

    def test_blocked_frames_shrink_too(self) -> None:
        width, block = 96, 24
        trits = [((i % 3) - 1) for i in range(width)]
        frame = dual6.pack_dual_plane_v2([0] * width, trits, block_symbols=block, flags=FLAG)
        bits, got, meta = dual6.unpack_dual_plane_v2(frame)
        self.assertEqual(got, trits)
        self.assertEqual(bits, [0] * width)
        self.assertEqual(meta["block_bytes"], (block + 4) // 5)
        self.assertEqual(meta["payload_len"], meta["block_count"] * meta["block_bytes"])

    def test_nonzero_bit_is_rejected_not_dropped(self) -> None:
        bits = [0] * 39 + [1]
        with self.assertRaises(Dual6Error) as ctx:
            dual6.pack_dual_plane_v2(bits, [0] * 40, flags=FLAG)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)

    def test_flag_survives_other_flag_bits(self) -> None:
        trits = [1] * 24
        frame = dual6.pack_dual_plane_v2([0] * 24, trits, flags=FLAG | 0b110)
        bits, got, meta = dual6.unpack_dual_plane_v2(frame)
        self.assertEqual((bits, got), ([0] * 24, trits))
        self.assertEqual(meta["flags"], FLAG | 0b110)

    def test_frame_auto_understands_the_flag(self) -> None:
        trits = [1, -1, 0, 1, 0]
        frame = dual6.pack_dual_plane_v2([0] * 5, trits, flags=FLAG)
        version, bits, got, meta = dual6.unpack_frame_auto(frame)
        self.assertEqual(version, 2)
        self.assertEqual(got, trits)
        self.assertEqual(bits, [0] * 5)

    def test_crc_still_covers_the_header(self) -> None:
        frame = bytearray(dual6.pack_dual_plane_v2([0] * 40, [1] * 40, flags=FLAG))
        frame[25] ^= 0x01  # touch payload_len
        with self.assertRaises(Dual6Error) as ctx:
            dual6.unpack_dual_plane_v2(bytes(frame))
        self.assertIn(ctx.exception.code, (ErrorCode.CRC_MISMATCH, ErrorCode.INVALID_LAYOUT))

    def test_old_frames_are_unaffected(self) -> None:
        # flags=0 must keep writing the bit plane (backwards compatible)
        frame = dual6.pack_dual_plane_v2([1] * 40, [1] * 40, flags=0)
        self.assertEqual(len(frame) - HEADER, (40 + 7) // 8 + (40 + 4) // 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
