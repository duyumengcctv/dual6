"""Tests for read-only channel views."""

from __future__ import annotations

import unittest

from dual6 import bit_view, mux, trit_view


class TestViews(unittest.TestCase):
    def test_views(self) -> None:
        bits = [1, 0, 1, 0]
        trits = [+1, -1, 0, 0]
        symbols = mux(bits, trits)

        bv = bit_view(symbols)
        tv = trit_view(symbols)

        self.assertEqual(len(bv), 4)
        self.assertEqual(len(tv), 4)
        self.assertEqual(list(bv), bits)
        self.assertEqual(list(tv), trits)
        self.assertEqual(bv[1:3], bits[1:3])
        self.assertEqual(tv[1:3], trits[1:3])
        self.assertEqual(bv.to_list(), bits)
        self.assertEqual(tv.to_list(), trits)


if __name__ == "__main__":
    unittest.main(verbosity=2)
