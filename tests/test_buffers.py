"""Tests for buffer / memoryview oriented helpers."""

from __future__ import annotations

import unittest

from dual6 import (
    Dual6Error,
    ErrorCode,
    pack_bits_bytes,
    pack_bits_into,
    pack_dual_plane_into,
    pack_trits_bytes,
    pack_trits_into,
    unpack_bits_from,
    unpack_dual_plane_from,
    unpack_trits_from,
)


class TestBitBuffer(unittest.TestCase):
    def test_roundtrip_with_offset(self) -> None:
        bits = [1, 0, 1, 0, 0, 1, 1, 0, 1]
        buf = bytearray(4)
        written = pack_bits_into(bits, buf, offset=1)
        self.assertEqual(written, 2)
        self.assertEqual(unpack_bits_from(buf, len(bits), offset=1), bits)

    def test_matches_bytes_helper(self) -> None:
        bits = [1, 0, 1, 0, 0, 1, 1]
        buf = bytearray(1)
        written = pack_bits_into(bits, buf)
        self.assertEqual(written, 1)
        self.assertEqual(bytes(buf), pack_bits_bytes(bits))

    def test_readonly_buffer(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_bits_into([1, 0], b"\x00\x00")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_buffer_too_small(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_bits_into([1] * 9, bytearray(1))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_nonzero_padding(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_bits_from(bytes([0b1000_0000]), 3)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


class TestTritBuffer(unittest.TestCase):
    def test_roundtrip_with_offset(self) -> None:
        trits = [1, -1, 0, 1, 0, -1]
        buf = bytearray(4)
        written = pack_trits_into(trits, buf, offset=1)
        self.assertEqual(written, 2)
        self.assertEqual(unpack_trits_from(buf, len(trits), offset=1), trits)

    def test_matches_bytes_helper(self) -> None:
        trits = [1, -1, 0, 1, 0, -1, 1]
        buf = bytearray((len(trits) + 4) // 5)
        pack_trits_into(trits, buf)
        self.assertEqual(bytes(buf), pack_trits_bytes(trits))

    def test_readonly_buffer(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_trits_into([1, 0], b"\x00")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_invalid_padding(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_trits_from(bytes([3]), 1)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


class TestDualPlaneBuffer(unittest.TestCase):
    def test_roundtrip(self) -> None:
        bits = [1, 0, 1, 0, 1]
        trits = [1, -1, 0, 0, 1]
        buf = bytearray(8)
        written = pack_dual_plane_into(bits, trits, buf, offset=1)
        self.assertEqual(written, (len(bits) + 7) // 8 + (len(bits) + 4) // 5)
        self.assertEqual(unpack_dual_plane_from(buf, len(bits), offset=1), (bits, trits))

    def test_width_mismatch(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_dual_plane_into([1, 0], [0], bytearray(4))
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)



if __name__ == "__main__":
    unittest.main(verbosity=2)
