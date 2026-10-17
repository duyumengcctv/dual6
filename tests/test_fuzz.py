"""Small deterministic fuzz / property tests.

These are not a replacement for a real fuzzer; they catch parser crashes and
obvious length / CRC regressions.
"""

from __future__ import annotations

import random
import unittest

from dual6 import (
    Dual6Error,
    ErrorCode,
    pack_dual_plane,
    pack_dual_plane_v1,
    pack_dual_plane_v2,
    unpack_dual_plane,
    unpack_dual_plane_v1,
    unpack_dual_plane_v2,
)


class TestFuzz(unittest.TestCase):
    def test_random_valid_roundtrips(self) -> None:
        rng = random.Random(99)
        for width in range(0, 65):
            bits = [rng.randrange(2) for _ in range(width)]
            trits = [rng.choice((-1, 0, 1)) for _ in range(width)]
            for pack, unpack in (
                (pack_dual_plane, unpack_dual_plane),
                (pack_dual_plane_v1, unpack_dual_plane_v1),
            ):
                frame = pack(bits, trits)
                self.assertEqual(unpack(frame), (bits, trits))
            frame = pack_dual_plane_v2(bits, trits)
            got_bits, got_trits, _ = unpack_dual_plane_v2(frame)
            self.assertEqual((got_bits, got_trits), (bits, trits))

    def test_random_truncation_raises(self) -> None:
        rng = random.Random(100)
        bits = [rng.randrange(2) for _ in range(37)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(37)]
        frames = [
            (pack_dual_plane(bits, trits), unpack_dual_plane),
            (pack_dual_plane_v1(bits, trits), unpack_dual_plane_v1),
            (pack_dual_plane_v2(bits, trits), unpack_dual_plane_v2),
        ]
        for frame, unpack in frames:
            for cut in range(len(frame)):
                with self.assertRaises(Dual6Error):
                    unpack(frame[:cut])

    def test_random_trash_raises(self) -> None:
        rng = random.Random(101)
        for _ in range(200):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 80)))
            with self.assertRaises(Dual6Error):
                unpack_dual_plane_v2(data)

    def test_crc_mutations(self) -> None:
        rng = random.Random(102)
        bits = [rng.randrange(2) for _ in range(64)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(64)]
        for pack, unpack in (
            (pack_dual_plane_v1, unpack_dual_plane_v1),
            (pack_dual_plane_v2, unpack_dual_plane_v2),
        ):
            base = bytearray(pack(bits, trits))
            for _ in range(50):
                frame = bytearray(base)
                pos = rng.randrange(len(frame))
                frame[pos] ^= 1 << rng.randrange(8)
                try:
                    unpack(bytes(frame))
                except Dual6Error as exc:
                    self.assertIn(
                        exc.code,
                        (
                            ErrorCode.CRC_MISMATCH,
                            ErrorCode.INVALID_LAYOUT,
                            ErrorCode.UNSUPPORTED_VERSION,
                        ),
                    )
                else:
                    self.fail("mutated frame decoded successfully")


if __name__ == "__main__":
    unittest.main(verbosity=2)
