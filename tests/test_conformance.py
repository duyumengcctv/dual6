"""Conformance harness tests.

The native backend is optional.  When ``dual6._native`` exists, these tests
compare it against ``dual6._ref``; otherwise they self-check the harness.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import dual6
import dual6.adapters as adapters
from dual6 import _ref
from dual6._conformance import run_conformance, self_check

ROOT = Path(__file__).resolve().parents[1]


def _native_exports() -> set[str]:
    rust = (ROOT / "crates" / "dual6-py" / "src" / "lib.rs").read_text(encoding="utf-8")
    return set(re.findall(r"wrap_pyfunction!\(([A-Za-z0-9_]+),\s*m\)", rust))


class _Recorder:
    """Proxy that records which attributes the harness touches."""

    def __init__(self, target, seen: set[str]) -> None:
        self._target = target
        self._seen = seen

    def __getattr__(self, name: str):
        self._seen.add(name)
        return getattr(self._target, name)


class TestConformanceHarness(unittest.TestCase):
    def test_self_check(self) -> None:
        self.assertEqual(self_check(_ref), [])

    def test_public_api_against_ref(self) -> None:
        # `dual6` layers `_native` over `_ref`; comparing it to `_ref` (plus the
        # adapter module) checks every function the native extension provides.
        mismatches = run_conformance(_ref, dual6, adapters)
        self.assertEqual(mismatches, [])

    def test_harness_covers_every_native_export(self) -> None:
        seen: set[str] = set()
        run_conformance(_ref, _Recorder(dual6, seen), adapters)
        missing = sorted(_native_exports() - seen)
        self.assertEqual(
            missing,
            [],
            f"_conformance.run_conformance never exercises: {missing}",
        )

    def test_harness_detects_a_broken_backend(self) -> None:
        class Broken:
            def __getattr__(self, name: str):
                return getattr(dual6, name)

            def decode_digit(self, digit: int):
                return (99, 99)

        mismatches = run_conformance(_ref, Broken())
        self.assertTrue(mismatches, "harness failed to notice a wrong decode_digit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
