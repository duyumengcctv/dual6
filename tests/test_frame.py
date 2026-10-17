"""Tests for D6P0 dual-plane frames."""

from __future__ import annotations

import random
import unittest

from dual6 import Dual6Error, ErrorCode, pack_dual_plane, unpack_dual_plane


class TestFrame(unittest.TestCase):
    def test_roundtrip(self) -> None:
        random.seed(4)
        for width in list(range(0, 20)) + [24, 40, 64, 129]:
            bits = [random.randrange(2) for _ in range(width)]
            trits = [random.choice((-1, 0, 1)) for _ in range(width)]
            frame = pack_dual_plane(bits, trits)
            self.assertEqual(unpack_dual_plane(frame), (bits, trits))

    def test_width_mismatch(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_dual_plane([0, 1], [0])
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)

    def test_bad_magic(self) -> None:
        frame = bytearray(pack_dual_plane([0], [0]))
        frame[0:4] = b"XXXX"
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_unsupported_version(self) -> None:
        frame = bytearray(pack_dual_plane([0], [0]))
        frame[4] = 99
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.UNSUPPORTED_VERSION)

    def test_truncated_frame(self) -> None:
        frame = pack_dual_plane([0, 1, 0], [1, -1, 0])
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane(frame[:-1])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
