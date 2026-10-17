"""Convenience launcher for environments where `python -m dual6` cannot see
the local `python/` source directory (for example isolated/safe-path Python).
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "python"))

from dual6.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
