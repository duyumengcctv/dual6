"""A1 · width preservation in the exact-dual codec.

``encode_number`` used to keep only ``max(len(binary), len(ternary))`` symbols,
so leading zeros vanished: ``from_bits([1, 0, 0, 0])`` decoded back as ``[1]``.
A storage container cannot silently change the width of what it stored.
"""

from __future__ import annotations

import random
import unittest

from dual6 import exact_dual as ed
from dual6 import Dual6Error, ErrorCode


class WidthPreservation(unittest.TestCase):
    def test_leading_zeros_survive(self) -> None:
        for bits in ([1, 0, 0, 0], [1] + [0] * 19, [0, 0, 1], [1, 0, 1, 0, 1, 0, 1]):
            with self.subTest(bits=bits):
                symbols = ed.from_bits(bits)
                self.assertEqual(len(symbols), len(bits))
                self.assertEqual(ed.to_bits(symbols), bits)

    def test_trits_keep_their_width_when_the_binary_side_is_shorter(self) -> None:
        # the symbol count is max(binary digits, ternary digits, trit width):
        # the bit channel can need more symbols than the trit list has, but
        # never fewer, so the trit prefix always round-trips
        for trits in ([1, 0, 0], [1, 1, 0, 0, 0], [0, 0, 1]):
            with self.subTest(trits=trits):
                symbols = ed.from_trits(trits)
                self.assertGreaterEqual(len(symbols), len(trits))
                self.assertEqual(ed.to_trits(symbols)[: len(trits)], trits)

    def test_roundtrip_over_random_widths(self) -> None:
        rng = random.Random(77)
        self.assertEqual(ed.from_bits([]), [])
        for width in range(0, 40):
            bits = [rng.randrange(2) for _ in range(width)]
            with self.subTest(width=width):
                symbols = ed.from_bits(bits)
                self.assertEqual(len(symbols), width)
                self.assertEqual(ed.to_bits(symbols), bits)
                self.assertEqual(ed.to_int(symbols), sum(b << i for i, b in enumerate(bits)))

    def test_padding_symbol_is_the_dual6_zero(self) -> None:
        symbols = ed.from_bits([1, 0, 0, 0])
        self.assertEqual(symbols[1:], [1, 1, 1])  # d = 1 -> (b=0, t=0)
        self.assertEqual(ed.read_binary(symbols), 1)
        self.assertEqual(ed.read_ternary(symbols), 1)

    def test_explicit_width_argument(self) -> None:
        self.assertEqual(len(ed.encode_number(0)), 1)
        self.assertEqual(len(ed.encode_number(0, width=8)), 8)
        self.assertEqual(ed.to_int(ed.encode_number(5, width=16)), 5)

    def test_bad_width_is_rejected(self) -> None:
        for bad in (-1, 1.5, "4", True):
            with self.subTest(width=bad):
                with self.assertRaises(Dual6Error) as ctx:
                    ed.encode_number(3, width=bad)
                self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_width_does_not_change_the_value(self) -> None:
        for n in (0, 1, 5, 255, 4096):
            for width in (0, 8, 32):
                with self.subTest(n=n, width=width):
                    self.assertEqual(ed.to_int(ed.encode_number(n, width=width)), n)


if __name__ == "__main__":
    unittest.main(verbosity=2)
