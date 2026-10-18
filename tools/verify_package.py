"""Build and verify the Dual6 Python package (wheel + sdist).

What this checks
----------------
* the wheel contains the complete ``dual6`` package (including ``_ref``,
  ``adapters``, ``py.typed`` and the native stub);
* the sdist contains the docs, benchmark data/charts, tools, tests and the
  golden vectors that the README links to;
* neither artifact contains bytecode or build output;
* optionally, the wheel installs into a throw-away virtual environment and
  performs a round-trip plus a CLI smoke test.

Usage
-----
    python tools/verify_package.py --build
    python tools/verify_package.py --build --install-test
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

WHEEL_REQUIRED = (
    "dual6/__init__.py",
    "dual6/cli.py",
    "dual6/py.typed",
    "dual6/_native.pyi",
    "dual6/_ref/__init__.py",
    "dual6/_ref/frame.py",
    "dual6/adapters/binary.py",
    "dual6/adapters/ternary.py",
)

SDIST_REQUIRED = (
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "pyproject.toml",
    "Cargo.toml",
    "dual6_cli.py",
    "run_tests.py",
    "docs/00-scope.md",
    "docs/13-use-cases.md",
    "docs/dual6-format.svg",
    "benchmarks/README.md",
    "benchmarks/fault_size.csv",
    "benchmarks/charts/scorecard.png",
    "tests/test_frame.py",
    "tests/vectors/golden_vectors.json",
    "tools/check_all.py",
    "tools/coverage.py",
    "tools/verify_package.py",
    "python/dual6/__init__.py",
    "crates/dual6-core/src/frame.rs",
)

BAD_SUFFIXES = (".pyc", ".pyo", ".pyd", ".so", ".dll", ".rlib", ".rmeta")


def _run(cmd: List[str], cwd: str = ROOT) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def build_artifacts(outdir: str) -> tuple[str, str]:
    os.makedirs(outdir, exist_ok=True)
    try:
        import build  # noqa: F401
    except ImportError:
        build = None
    if build is not None:
        _run([sys.executable, "-m", "build", "--outdir", outdir, ROOT])
    else:
        # Fallback for environments without the ``build`` frontend.
        code = (
            "import setuptools.build_meta as b;"
            f"print(b.build_wheel({outdir!r}));"
            f"print(b.build_sdist({outdir!r}))"
        )
        _run([sys.executable, "-c", code])

    wheels = [f for f in os.listdir(outdir) if f.endswith(".whl")]
    sdists = [f for f in os.listdir(outdir) if f.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(f"expected one wheel and one sdist in {outdir}, got {wheels} / {sdists}")
    return os.path.join(outdir, wheels[0]), os.path.join(outdir, sdists[0])


def _inside(name: str, root: str) -> str:
    return name.split(root, 1)[-1].lstrip("/")


def verify_wheel(path: str) -> None:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        bad = [n for n in names if n.endswith(BAD_SUFFIXES) or "__pycache__" in n]
        if bad:
            raise SystemExit(f"wheel contains build/bytecode artifacts: {bad[:5]}")
        missing = [n for n in WHEEL_REQUIRED if n not in names]
        if missing:
            raise SystemExit(f"wheel is missing required files: {missing}")
    print(f"ok: wheel {os.path.basename(path)} ({len(names)} files)")


def verify_sdist(path: str) -> None:
    with tarfile.open(path) as tf:
        names = [m.name for m in tf.getmembers() if m.isfile()]
    roots = {n.split("/", 1)[0] for n in names}
    root = sorted(roots)[0] + "/"
    rel = {_inside(n, root) for n in names}
    bad = [n for n in names if n.endswith(BAD_SUFFIXES) or "__pycache__" in n]
    if bad:
        raise SystemExit(f"sdist contains build/bytecode artifacts: {bad[:5]}")
    missing = [n for n in SDIST_REQUIRED if n not in rel]
    if missing:
        raise SystemExit(f"sdist is missing required files: {missing}")
    print(f"ok: sdist {os.path.basename(path)} ({len(names)} files)")


def _venv_python(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


SMOKE = """\
import dual6

bits = [1, 0, 1, 1]
trits = [1, -1, 0, 1]
symbols = dual6.mux(bits, trits)
assert dual6.demux(symbols) == (bits, trits)
frame = dual6.pack_dual_plane_v2(bits, trits)
assert dual6.unpack_dual_plane_v2(frame)[:2] == (bits, trits)
assert dual6.__version__ == "0.3.0"
print("smoke ok", dual6.__version__, dual6.__backend__)
"""


def install_test(wheel: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        venv_dir = os.path.join(tmp, "venv")
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        py = _venv_python(venv_dir)
        _run([py, "-m", "pip", "install", "--no-index", "--no-deps", wheel], cwd=tmp)
        _run([py, "-c", SMOKE], cwd=tmp)
        _run([py, "-m", "dual6", "info"], cwd=tmp)
        _run([py, "-m", "dual6", "encode", "--bits", "1011", "--trits", "P-TP"], cwd=tmp)
    print("ok: wheel installs and runs in a fresh venv")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="build fresh wheel + sdist")
    parser.add_argument(
        "--install-test",
        action="store_true",
        help="install the wheel into a fresh venv and run smoke tests",
    )
    parser.add_argument("--outdir", default=DIST, help=f"artifact directory (default: {DIST})")
    args = parser.parse_args(argv)

    if args.build:
        outdir = args.outdir
        if os.path.isdir(outdir):
            shutil.rmtree(outdir)
        wheel, sdist = build_artifacts(outdir)
    else:
        wheels = sorted(
            os.path.join(args.outdir, f)
            for f in os.listdir(args.outdir)
            if f.endswith(".whl")
        ) if os.path.isdir(args.outdir) else []
        sdists = sorted(
            os.path.join(args.outdir, f)
            for f in os.listdir(args.outdir)
            if f.endswith(".tar.gz")
        ) if os.path.isdir(args.outdir) else []
        if not wheels or not sdists:
            raise SystemExit("no artifacts found; pass --build to create them")
        wheel, sdist = wheels[-1], sdists[-1]

    verify_wheel(wheel)
    verify_sdist(sdist)
    if args.install_test:
        install_test(wheel)
    print("package verification OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
