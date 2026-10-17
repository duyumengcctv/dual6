"""The tool is an exchange layer: one side encodes, the other decodes losslessly."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from dual6.exact_dual import (
    from_balanced_ternary,
    from_bits,
    from_trits,
    to_balanced_ternary,
    to_binary_digits,
    to_bits,
    to_int,
    to_trits,
)

ROOT = Path(__file__).resolve().parents[1]


def bits_to_int(bits):
    return sum(b << i for i, b in enumerate(bits))


class TestEngineExchange(unittest.TestCase):
    def test_binary_engine_encodes_ternary_engine_decodes(self) -> None:
        n = 42 + 7
        symbols = from_bits(to_binary_digits(n))
        self.assertEqual(from_balanced_ternary(to_trits(symbols)), n)
        self.assertEqual(to_int(symbols), n)

    def test_ternary_engine_encodes_binary_engine_decodes(self) -> None:
        n = 49 + 49
        symbols = from_trits(to_balanced_ternary(n))
        self.assertEqual(bits_to_int(to_bits(symbols)), n)
        self.assertEqual(to_int(symbols), n)

    def test_callers_never_pass_two_expansions(self) -> None:
        # from_bits takes only bits; from_trits takes only trits.
        self.assertEqual(to_int(from_bits([0, 1, 0, 1, 0, 1])), 42)
        self.assertEqual(to_int(from_trits([0, -1, -1, -1, 1])), 42)

    def test_one_sided_write_is_not_a_lossless_handoff(self) -> None:
        d = 3 * 1 + (0 + 1)          # binary wrote 1, trit left at default 0
        self.assertEqual(to_bits([d]), [1])
        self.assertEqual(to_trits([d]), [0])   # ternary side sees default 0, not 1

    def test_example_script_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "engine_exchange.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("另一边自动无损解码", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
