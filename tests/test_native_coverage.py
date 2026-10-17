"""Native (PyO3) API coverage guards.

These tests keep ``_native.pyi``, the Rust module and the reference package in
sync.  They run without a compiled native extension because they only read the
Rust source and the stub file.
"""

from __future__ import annotations

import unittest

from tools import native_coverage


class TestNativeCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.info = native_coverage.analyse()

    def test_stub_matches_rust_exports(self) -> None:
        self.assertEqual(
            sorted(self.info["stub"]),
            sorted(self.info["native"]),
            "python/dual6/_native.pyi must declare exactly the #[pyfunction] exports",
        )

    def test_no_eligible_callable_fell_back_to_python(self) -> None:
        self.assertEqual(self.info["eligible_missing"], [])

    def test_allow_list_is_not_stale(self) -> None:
        self.assertEqual(self.info["stale_allow"], [])

    def test_every_native_name_is_a_public_callable(self) -> None:
        public = self.info["public"]
        native = self.info["native"]
        unknown = sorted(native - public)
        self.assertEqual(unknown, [], f"native exports not reachable as dual6 public callables: {unknown}")

    def test_coverage_baseline(self) -> None:
        # Regression floor: the native data path must not shrink below 49.
        self.assertGreaterEqual(len(self.info["native"]), 49)
        self.assertGreaterEqual(len(self.info["universe"]), 67)


if __name__ == "__main__":
    unittest.main(verbosity=2)
