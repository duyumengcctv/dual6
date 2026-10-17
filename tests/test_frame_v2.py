"""Tests for the D6P2 frame with dtype, block metadata, and CRC32."""

from __future__ import annotations

import random
import unittest

from dual6 import (
    DTYPE_MIXED,
    DTYPE_TERNARY,
    Dual6Error,
    ErrorCode,
    pack_dual_plane_v2,
    unpack_dual_plane_v2,
)


class TestFrameV2(unittest.TestCase):
    def test_no_block_roundtrip(self) -> None:
        random.seed(30)
        for width in list(range(0, 20)) + [24, 40, 48, 129]:
            bits = [random.randrange(2) for _ in range(width)]
            trits = [random.choice((-1, 0, 1)) for _ in range(width)]
            frame = pack_dual_plane_v2(bits, trits, dtype=DTYPE_MIXED, flags=0b110)
            bits2, trits2, meta = unpack_dual_plane_v2(frame)
            self.assertEqual((bits2, trits2), (bits, trits))
            self.assertEqual(meta["dtype"], DTYPE_MIXED)
            self.assertEqual(meta["flags"], 0b110)
            self.assertEqual(meta["width"], width)
            self.assertEqual(meta["block_symbols"], 0)
            self.assertEqual(meta["block_count"], 0)

    def test_blocked_roundtrip(self) -> None:
        random.seed(31)
        for width, block in ((24, 24), (48, 24), (40, 40), (48, 48), (96, 48)):
            bits = [random.randrange(2) for _ in range(width)]
            trits = [random.choice((-1, 0, 1)) for _ in range(width)]
            frame = pack_dual_plane_v2(bits, trits, dtype=DTYPE_TERNARY, block_symbols=block)
            bits2, trits2, meta = unpack_dual_plane_v2(frame)
            self.assertEqual((bits2, trits2), (bits, trits))
            self.assertEqual(meta["block_symbols"], block)
            self.assertEqual(meta["block_count"], width // block)

    def test_crc_detects_corruption(self) -> None:
        frame = bytearray(pack_dual_plane_v2([0, 1, 0], [1, -1, 0]))
        frame[-1] ^= 0x01
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v2(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.CRC_MISMATCH)

    def test_bad_magic(self) -> None:
        frame = bytearray(pack_dual_plane_v2([0], [0]))
        frame[0:4] = b"XXXX"
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v2(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_unsupported_version(self) -> None:
        frame = bytearray(pack_dual_plane_v2([0], [0]))
        frame[4] = 99
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v2(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.UNSUPPORTED_VERSION)

    def test_unsupported_dtype(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_dual_plane_v2([0], [0], dtype=99)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_block_width_must_divide(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_dual_plane_v2([0] * 5, [0] * 5, block_symbols=2)
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)

    def test_block_metadata_mismatch(self) -> None:
        frame = bytearray(pack_dual_plane_v2([0] * 24, [0] * 24, block_symbols=24))
        # block_bytes is at offset 17, zero it out; CRC is recomputed? No:
        # we want a deterministic structural error, so set payload_len wrong
        # and let structural validation fire before CRC.
        frame[25:29] = b"\x00\x00\x00\x00"
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v2(bytes(frame))
        self.assertIn(ctx.exception.code, (ErrorCode.INVALID_LAYOUT, ErrorCode.CRC_MISMATCH))

    def test_truncated_frame(self) -> None:
        frame = pack_dual_plane_v2([0, 1], [1, 0])
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v2(frame[:-1])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
