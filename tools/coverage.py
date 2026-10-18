"""Run the Dual6 test suite under coverage.

The CI ``ref`` job installs the ``dev`` extra (which includes ``coverage``)
and calls ``python tools/coverage.py --html``.

Exit status is non-zero when the tests fail.  ``--fail-under`` can additionally
enforce a minimum total coverage percentage.
"""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from typing import List, Optional

# Running this file as a script puts ``tools/`` at the front of ``sys.path``,
# which would make ``import coverage`` import this very file.  Drop it first so
# the real third-party package wins, then add the project paths we need.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)

ROOT = os.path.dirname(_SCRIPT_DIR)
SRC = os.path.join(ROOT, "python")
TESTS = os.path.join(ROOT, "tests")

for path in (SRC, TESTS, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


def _suite() -> unittest.TestSuite:
    return unittest.defaultTestLoader.discover(TESTS, pattern="test_*.py", top_level_dir=ROOT)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", action="store_true", help="write an HTML report to htmlcov/")
    parser.add_argument("--xml", action="store_true", help="write coverage.xml")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        help="fail if total coverage is below this percentage (default: 0)",
    )
    args = parser.parse_args(argv)

    try:
        import coverage
    except ImportError:
        print(
            "coverage is not installed; run `python -m pip install coverage` "
            "or install the dev extra: `python -m pip install -e '.[dev]'`",
            file=sys.stderr,
        )
        return 1

    cov = coverage.Coverage(source=["dual6"], branch=False)
    cov.start()
    try:
        result = unittest.TextTestRunner(verbosity=2).run(_suite())
    finally:
        cov.stop()
        cov.save()

    print("\n== coverage ==")
    total = cov.report(show_missing=True, skip_covered=False)
    if args.html:
        cov.html_report(directory=os.path.join(ROOT, "htmlcov"))
        print("HTML report: htmlcov/index.html")
    if args.xml:
        cov.xml_report(outfile=os.path.join(ROOT, "coverage.xml"))

    if not result.wasSuccessful():
        return 1
    if args.fail_under and total < args.fail_under:
        print(f"coverage {total:.1f}% is below --fail-under {args.fail_under:.1f}%")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
