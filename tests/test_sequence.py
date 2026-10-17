"""Tests for sequence-level mux/demux."""

from __future__ import annotations

import random
import unittest

from dual6 import Dual6Error, ErrorCode, demux, mux


class TestSequence(unittest.TestCase):
    def test_mux_demux_roundtrip(self) -> None:
        random.seed(0)
        for width in list(range(0, 10)) + [24, 40]:
            bits = [random.randrange(2) for _ in range(width)]
            trits = [random.choice((-1, 0, 1)) for _ in range(width)]
            symbols = mux(bits, trits)
            self.assertEqual(len(symbols), width)
            self.assertEqual(demux(symbols), (bits, trits))

    def test_zero_representation(self) -> None:
        self.assertEqual(mux([0, 0, 0], [0, 0, 0]), [1, 1, 1])

    def test_width_mismatch(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            mux([0, 1], [0])
        self.assertEqual(ctx.exception.code, ErrorCode.WIDTH_MISMATCH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
