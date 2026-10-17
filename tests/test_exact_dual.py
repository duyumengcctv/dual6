"""Tests for the exact dual-expansion codec (``dual6.exact_dual``).

One integer N -> one symbol sequence; the binary view (``d//3``) and the
balanced-ternary view (``d%3-1``) both reconstruct N exactly.
"""

from __future__ import annotations

import math
import os
import random
import struct
import subprocess
import sys
import unittest
from pathlib import Path

from dual6 import Dual6Error, ErrorCode
from dual6.exact_dual import (
    decode_bytes,
    decode_f64,
    encode_bytes,
    encode_f64,
    encode_number,
    from_balanced_ternary,
    from_bits,
    from_trits,
    read_binary,
    read_ternary,
    to_balanced_ternary,
    to_binary_digits,
    to_bits,
    to_int,
    to_trits,
)

ROOT = Path(__file__).resolve().parents[1]


class TestDigitExpansions(unittest.TestCase):
    def test_binary_digits(self) -> None:
        for n in range(2000):
            digits = to_binary_digits(n)
            self.assertEqual(sum(b << i for i, b in enumerate(digits)), n)

    def test_balanced_ternary_roundtrip(self) -> None:
        for n in range(2000):
            trits = to_balanced_ternary(n)
            self.assertTrue(all(t in (-1, 0, 1) for t in trits))
            self.assertEqual(from_balanced_ternary(trits), n)

    def test_balanced_ternary_rejects_bad_digit(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            from_balanced_ternary([0, 2])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_TRIT)


class TestCodec(unittest.TestCase):
    def test_symbols_are_six_state(self) -> None:
        for n in list(range(500)) + [2 ** 64 + 12345, 10 ** 40]:
            for d in encode_number(n):
                self.assertIn(d, range(6))

    def test_both_views_reconstruct_small_range(self) -> None:
        for n in range(10000):
            symbols = encode_number(n)
            self.assertEqual(read_binary(symbols), n, f"binary view failed at {n}")
            self.assertEqual(read_ternary(symbols), n, f"ternary view failed at {n}")

    def test_both_views_reconstruct_large_values(self) -> None:
        for n in (2 ** 64 + 12345, 10 ** 40 + 7, 2 ** 200 - 1, 6 ** 100):
            symbols = encode_number(n)
            self.assertEqual(read_binary(symbols), n)
            self.assertEqual(read_ternary(symbols), n)

    def test_encoding_is_injective(self) -> None:
        seen: dict[tuple[int, ...], int] = {}
        for n in range(3000):
            key = tuple(encode_number(n))
            self.assertNotIn(key, seen, f"collision between {seen.get(key)} and {n}")
            seen[key] = n

    def test_symbol_count_is_max_of_two_expansions(self) -> None:
        for n in range(1000):
            expected = max(len(to_binary_digits(n)), len(to_balanced_ternary(n)))
            self.assertEqual(len(encode_number(n)), expected)

    def test_padding_with_dual6_zero_preserves_value(self) -> None:
        # d = 1 is (bit=0, trit=0); padding with it must not change N.
        for n in (0, 1, 42, 2 ** 64 + 12345):
            padded = encode_number(n) + [1] * 7
            self.assertEqual(read_binary(padded), n)
            self.assertEqual(read_ternary(padded), n)

    def test_negative_number_is_rejected(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            encode_number(-1)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_bad_symbol_is_rejected(self) -> None:
        for fn in (read_binary, read_ternary):
            with self.assertRaises(Dual6Error) as ctx:
                fn([0, 6, 1])
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_DIGIT)


class TestFloatAndBytes(unittest.TestCase):
    def test_f64_roundtrip(self) -> None:
        for value in (0.0, -0.0, 3.141592653589793, -0.1, 1e300, -1e-300, math.inf, -math.inf):
            symbols = encode_f64(value)
            got = decode_f64(symbols)
            self.assertEqual(
                struct.pack("<d", got),
                struct.pack("<d", value),
                f"f64 mismatch for {value!r}",
            )

    def test_nan_bits_are_preserved(self) -> None:
        symbols = encode_f64(math.nan)
        self.assertTrue(math.isnan(decode_f64(symbols)))

    def test_bytes_roundtrip(self) -> None:
        rng = random.Random(11)
        for size in (0, 1, 7, 8, 33, 256):
            data = bytes(rng.randrange(256) for _ in range(size))
            symbols = encode_bytes(data)
            self.assertEqual(decode_bytes(symbols, size), data)

    def test_decode_bytes_too_small_is_rejected(self) -> None:
        symbols = encode_bytes(b"\xff\xff")
        with self.assertRaises(Dual6Error) as ctx:
            decode_bytes(symbols, 1)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)

    def test_decode_bytes_negative_size_is_rejected(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            decode_bytes([1], -1)
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


class TestFriendlyApi(unittest.TestCase):
    def test_from_bits_and_to_bits(self) -> None:
        for n in (0, 1, 42, 2 ** 64 + 12345):
            bits = to_binary_digits(n)
            symbols = from_bits(bits)
            self.assertEqual(to_int(symbols), n)
            self.assertEqual(bits_to_int(to_bits(symbols)), n)

    def test_from_trits_and_to_trits(self) -> None:
        for n in (0, 1, 42, 2 ** 64 + 12345):
            trits = to_balanced_ternary(n)
            symbols = from_trits(trits)
            self.assertEqual(to_int(symbols), n)
            self.assertEqual(from_balanced_ternary(to_trits(symbols)), n)

    def test_from_bits_rejects_bad_bit(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            from_bits([0, 2])
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_BIT)

    def test_to_int_rejects_non_exact_dual(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            to_int([0])          # binary view 0, ternary view -1
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


def bits_to_int(bits):
    return sum(b << i for i, b in enumerate(bits))


class TestExample(unittest.TestCase):
    def test_example_script_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "dual_read_number.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("全量对拍", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
