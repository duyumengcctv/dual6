"""Backend selection (DUAL6_BACKEND) tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYDIR = ROOT / "python"

import dual6  # noqa: E402


def run_py(code: str, backend: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("DUAL6_BACKEND", None)
    if backend is not None:
        env["DUAL6_BACKEND"] = backend
    bootstrap = f"import sys; sys.path.insert(0, {str(PYDIR)!r}); "
    return subprocess.run(
        [sys.executable, "-c", bootstrap + code],
        capture_output=True,
        text=True,
        env=env,
    )


class TestBackendSelection(unittest.TestCase):
    def test_backend_attribute_matches_loaded_module(self) -> None:
        expected = "native" if getattr(dual6, "_native_module", None) is not None else "ref"
        self.assertEqual(dual6.__backend__, expected)

    def test_default_reports_a_known_backend(self) -> None:
        result = run_py("import dual6; print(dual6.__backend__)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(result.stdout.strip(), ("ref", "native"))

    def test_forced_ref_never_loads_native(self) -> None:
        result = run_py("import dual6; print(dual6.__backend__, dual6._native_module)", backend="ref")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ref None")

    def test_forced_native_requires_extension(self) -> None:
        result = run_py("import dual6; print(dual6.__backend__)", backend="native")
        if result.returncode == 0:
            self.assertEqual(result.stdout.strip(), "native")
        else:
            self.assertIn("dual6._native is not importable", result.stderr)

    def test_invalid_backend_is_rejected(self) -> None:
        result = run_py("import dual6", backend="bogus")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DUAL6_BACKEND must be one of", result.stderr)

    def test_cli_info_reports_backend(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "dual6_cli.py"), "info"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["backend"], dual6.__backend__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
