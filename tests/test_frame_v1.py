"""Tests for the D6P1 frame with CRC32."""

from __future__ import annotations

import random
import struct
import unittest

from dual6 import (
    Dual6Error,
    ErrorCode,
    pack_dual_plane_v1,
    unpack_dual_plane_v1,
)


class TestFrameV1(unittest.TestCase):
    def test_roundtrip(self) -> None:
        random.seed(5)
        for width in list(range(0, 20)) + [24, 40, 64, 129]:
            bits = [random.randrange(2) for _ in range(width)]
            trits = [random.choice((-1, 0, 1)) for _ in range(width)]
            frame = pack_dual_plane_v1(bits, trits)
            self.assertEqual(unpack_dual_plane_v1(frame), (bits, trits))

    def test_crc_detects_payload_corruption(self) -> None:
        frame = bytearray(pack_dual_plane_v1([0, 1, 0], [1, -1, 0]))
        frame[-1] ^= 0x01
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.CRC_MISMATCH)

    def test_crc_detects_header_corruption(self) -> None:
        frame = bytearray(pack_dual_plane_v1([0, 1, 0], [1, -1, 0]))
        frame[8] ^= 0x01  # width field, also covered by CRC
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.CRC_MISMATCH)

    def test_bad_magic(self) -> None:
        frame = bytearray(pack_dual_plane_v1([0], [0]))
        frame[0:4] = b"XXXX"
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_unsupported_version(self) -> None:
        frame = bytearray(pack_dual_plane_v1([0], [0]))
        frame[4] = 99
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.UNSUPPORTED_VERSION)

    def test_reserved_must_be_zero(self) -> None:
        frame = bytearray(pack_dual_plane_v1([0], [0]))
        struct.pack_into("<H", frame, 6, 1)
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(bytes(frame))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_truncated_frame(self) -> None:
        frame = pack_dual_plane_v1([0, 1], [1, 0])
        with self.assertRaises(Dual6Error) as ctx:
            unpack_dual_plane_v1(frame[:-1])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
