"""Tests for the optional exact-dual arithmetic layer (``dual6.arithmetic``)."""

from __future__ import annotations

import random
import unittest

from dual6 import Dual6Error, ErrorCode
from dual6.arithmetic import add, add_digits, divmod, mul, sub
from dual6.exact_dual import encode_number, read_binary, read_ternary


class TestValueLevelArithmetic(unittest.TestCase):
    def test_add(self) -> None:
        rng = random.Random(1)
        for _ in range(500):
            x, y = rng.randrange(0, 20000), rng.randrange(0, 20000)
            result = add(encode_number(x), encode_number(y))
            self.assertEqual(read_binary(result), x + y)
            self.assertEqual(read_ternary(result), x + y)

    def test_sub(self) -> None:
        rng = random.Random(2)
        for _ in range(500):
            x, y = rng.randrange(0, 20000), rng.randrange(0, 20000)
            if x < y:
                x, y = y, x
            result = sub(encode_number(x), encode_number(y))
            self.assertEqual(read_binary(result), x - y)
            self.assertEqual(read_ternary(result), x - y)

    def test_mul(self) -> None:
        rng = random.Random(3)
        for _ in range(300):
            x, y = rng.randrange(0, 5000), rng.randrange(0, 5000)
            result = mul(encode_number(x), encode_number(y))
            self.assertEqual(read_binary(result), x * y)
            self.assertEqual(read_ternary(result), x * y)

    def test_divmod(self) -> None:
        rng = random.Random(4)
        for _ in range(500):
            x, y = rng.randrange(0, 20000), rng.randrange(1, 500)
            quotient, remainder = divmod(encode_number(x), encode_number(y))
            self.assertEqual(read_binary(quotient), x // y)
            self.assertEqual(read_binary(remainder), x % y)
            self.assertEqual(read_ternary(quotient), x // y)
            self.assertEqual(read_ternary(remainder), x % y)

    def test_results_are_exact_dual(self) -> None:
        result = add(encode_number(42), encode_number(7))
        self.assertEqual(read_binary(result), read_ternary(result))
        self.assertTrue(all(0 <= d <= 5 for d in result))


class TestDigitLevelAddition(unittest.TestCase):
    def test_add_digits_matches_value_level(self) -> None:
        rng = random.Random(5)
        for _ in range(1000):
            x, y = rng.randrange(0, 30000), rng.randrange(0, 30000)
            a, b = encode_number(x), encode_number(y)
            self.assertEqual(add_digits(a, b), add(a, b), f"{x}+{y}")

    def test_carry_cases(self) -> None:
        cases = [(1, 1), (3, 1), (5, 5), (31, 1), (6 ** 5, 1), (2 ** 64, 2 ** 64)]
        for x, y in cases:
            a, b = encode_number(x), encode_number(y)
            result = add_digits(a, b)
            self.assertEqual(read_binary(result), x + y)
            self.assertEqual(read_ternary(result), x + y)


class TestErrors(unittest.TestCase):
    def test_negative_result_rejected(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            sub(encode_number(1), encode_number(2))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_division_by_zero_rejected(self) -> None:
        with self.assertRaises(Dual6Error) as ctx:
            divmod(encode_number(1), encode_number(0))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_PACKING)

    def test_non_exact_dual_operand_rejected(self) -> None:
        # d = 0 is (bit=0, trit=-1): binary view 0, ternary view -1.
        with self.assertRaises(Dual6Error) as ctx:
            add([0], encode_number(1))
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_LAYOUT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
