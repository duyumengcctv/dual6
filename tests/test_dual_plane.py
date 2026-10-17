"""Tests for bit/trit dual-plane byte packing."""

from __future__ import annotations

import random
import unittest

from dual6 import (
    Dual6Error,
    ErrorCode,
    pack_bits_bytes,
    pack_trits_bytes,
    unpack_bits_bytes,
    unpack_trits_bytes,
)


class TestBitPlane(unittest.TestCase):
    def test_roundtrip(self) -> None:
        random.seed(2)
        for width in range(0, 129):
            bits = [random.randrange(2) for _ in range(width)]
            data = pack_bits_bytes(bits)
            self.assertEqual(len(data), (width + 7) // 8)
            self.assertEqual(unpack_bits_bytes(data, width), bits)

    def test_padding_must_be_zero(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_bits_bytes(bytes([0b1000_0000]), 3)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_wrong_length(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_bits_bytes(b"\x00", 9)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


class TestTritPlane(unittest.TestCase):
    def test_roundtrip(self) -> None:
        random.seed(3)
        for width in range(0, 129):
            trits = [random.choice((-1, 0, 1)) for _ in range(width)]
            data = pack_trits_bytes(trits)
            self.assertEqual(len(data), (width + 4) // 5)
            self.assertEqual(unpack_trits_bytes(data, width), trits)

    def test_known_group(self) -> None:
        self.assertEqual(pack_trits_bytes([-1] * 5), b"\x00")
        self.assertEqual(pack_trits_bytes([+1] * 5), bytes([242]))

    def test_invalid_padding(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_trits_bytes(bytes([3]), 1)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_wrong_length(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_trits_bytes(b"", 1)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
