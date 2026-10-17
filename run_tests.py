"""Run all Dual6 tests.

The bundled Windows Python may run in isolated/safe-path mode, so this runner
explicitly adds ``src`` and the project root to ``sys.path`` before discovery.
"""

from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "python")
TESTS = os.path.join(HERE, "tests")

for path in (SRC, TESTS, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(TESTS, pattern="test_*.py", top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
