"""Single release gate for the Dual6 repository.

Runs every check that has to pass before a release:

* version strings agree across Cargo / pyproject / Python;
* the native stub and the Rust extension expose the same callables;
* the Rust workspace tests and build (unless ``--skip-rust``);
* the Python test suite on the selected backend.

The CI ``ref`` matrix calls this with ``--skip-rust``; the ``native`` job
builds the extension first and then calls it with ``DUAL6_BACKEND=native``.

Examples
--------
    python tools/check_all.py
    python tools/check_all.py --skip-rust
    DUAL6_BACKEND=native python tools/check_all.py --skip-rust
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(label: str, cmd: List[str], env: Optional[dict[str, str]] = None) -> bool:
    print(f"\n== {label} ==")
    printable = " ".join(cmd)
    print(f"+ {printable}")
    result = subprocess.run(cmd, cwd=ROOT, env=env, check=False)
    if result.returncode != 0:
        print(f"FAILED: {label} (exit code {result.returncode})")
        return False
    print(f"ok: {label}")
    return True


def _backend() -> str:
    code = "import dual6; print(dual6.__backend__)"
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", os.path.join(ROOT, "python"))
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-rust",
        action="store_true",
        help="skip cargo test/build (portable pure-Python CI job)",
    )
    args = parser.parse_args(argv)

    print(f"backend: {_backend()}")
    checks = [
        ("version strings", [sys.executable, "tools/check_version.py"]),
        ("native API coverage", [sys.executable, "tools/native_coverage.py"]),
        ("derived scorecard data", [sys.executable, "tools/make_scores.py", "--check"]),
    ]

    if args.skip_rust:
        print("rust: skipped (--skip-rust)")
    else:
        cargo = shutil.which("cargo")
        if cargo is None:
            print("FAILED: cargo not found on PATH (use --skip-rust for the portable job)")
            return 1
        checks.extend(
            [
                ("rust tests", [cargo, "test", "--workspace"]),
                ("rust build", [cargo, "build", "--workspace"]),
            ]
        )

    checks.append(("python tests", [sys.executable, "run_tests.py"]))

    failed = [label for label, cmd in checks if not _run(label, cmd)]
    if failed:
        print("\nrelease gate FAILED:")
        for label in failed:
            print(f"  - {label}")
        return 1
    print("\nrelease gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
