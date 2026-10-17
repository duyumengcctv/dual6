"""Version consistency test."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestVersion(unittest.TestCase):
    def test_version_consistency(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "check_version.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
