"""Explicit tests for native-backed adapter functions when available."""

from __future__ import annotations

import unittest

import dual6


class TestNativeAdapters(unittest.TestCase):
    def test_top_level_ternary_adapters(self) -> None:
        if not hasattr(dual6, "trits_to_symbols"):
            self.skipTest("native top-level adapters not available")
        trits = [1, -1, 0, 1, 0, -1]
        symbols = dual6.trits_to_symbols(trits)
        self.assertEqual(dual6.symbols_to_trits(symbols), trits)

    def test_top_level_binary_adapters(self) -> None:
        if not hasattr(dual6, "bits_to_symbols"):
            self.skipTest("native top-level adapters not available")
        bits = [1, 0, 1, 0, 0, 1]
        symbols = dual6.bits_to_symbols(bits)
        self.assertEqual(dual6.symbols_to_bits(symbols), bits)

    def test_top_level_block64_adapters(self) -> None:
        if not hasattr(dual6, "trits_to_dual6_block64"):
            self.skipTest("native top-level adapters not available")
        trits = [1, -1, 0] * 8
        data = dual6.trits_to_dual6_block64(trits)
        self.assertEqual(dual6.dual6_block64_to_trits(data), trits)

        bits = [1, 0] * 12
        data = dual6.bits_to_dual6_block64(bits)
        self.assertEqual(dual6.dual6_block64_to_bits(data), bits)


if __name__ == "__main__":
    unittest.main(verbosity=2)
