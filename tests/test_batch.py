"""Batch API: one call packs/unpacks many D6-64 blocks."""

from __future__ import annotations

import random
import unittest

from dual6 import (
    Dual6Error,
    ErrorCode,
    pack_block64,
    pack_block64_many,
    pack_block64_many_into,
    unpack_block64,
    unpack_block64_many,
    unpack_block64_many_into,
)


class TestBatchBlocks(unittest.TestCase):
    def test_roundtrip(self) -> None:
        rng = random.Random(1)
        for blocks in (0, 1, 2, 7, 64):
            symbols = [rng.randrange(6) for _ in range(24 * blocks)]
            packed = pack_block64_many(symbols)
            self.assertEqual(len(packed), 8 * blocks)
            self.assertEqual(unpack_block64_many(packed), symbols)

    def test_matches_single_block_calls(self) -> None:
        rng = random.Random(2)
        symbols = [rng.randrange(6) for _ in range(24 * 10)]
        packed = pack_block64_many(symbols)
        expected = b"".join(
            pack_block64(symbols[i : i + 24]) for i in range(0, len(symbols), 24)
        )
        self.assertEqual(packed, expected)
        self.assertEqual(
            unpack_block64_many(packed),
            [d for i in range(0, len(symbols), 24) for d in unpack_block64(packed[i // 3 : i // 3 + 8])],
        )

    def test_buffer_roundtrip(self) -> None:
        rng = random.Random(3)
        symbols = [rng.randrange(6) for _ in range(24 * 7)]
        packed = bytearray(8 * 7 + 4)
        written = pack_block64_many_into(bytes(symbols), packed, offset=4)
        self.assertEqual(written, 8 * 7)
        self.assertEqual(bytes(packed[4 : 4 + written]), pack_block64_many(symbols))

        out = bytearray(24 * 7 + 5)
        count = unpack_block64_many_into(bytes(packed[4 : 4 + written]), out, offset=5)
        self.assertEqual(count, 24 * 7)
        self.assertEqual(list(out[5 : 5 + count]), symbols)

    def test_buffer_too_small(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_block64_many_into(bytes([0] * 24), bytearray(4))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_bad_symbol_count(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            pack_block64_many([0] * 23)
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)

    def test_bad_byte_count(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            unpack_block64_many(b"\x00" * 7)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_empty_batch(self) -> None:
        self.assertEqual(pack_block64_many([]), b"")
        self.assertEqual(unpack_block64_many(b""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
