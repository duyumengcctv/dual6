r"""Build the Dual6 PyO3 native extension.

Typical Windows use:

    python tools/build_native.py --python C:\Python311\python.exe

The script:
  1. cleans broken empty proxy variables,
  2. locates cargo,
  3. runs `cargo test --workspace`,
  4. builds `crates/dual6-py`,
  5. copies the extension into `python/dual6/`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_PKG = ROOT / "python" / "dual6"


def find_cargo() -> str:
    candidates = [
        Path("C:/Users/Administrator/dual6-rust/toolchain/bin/cargo.exe"),
        Path(os.environ.get("USERPROFILE", "")) / ".cargo" / "bin" / "cargo.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("cargo")
    if found:
        return found
    raise SystemExit("cargo not found; add Rust toolchain to PATH or install it first")


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        env.pop(key, None)
    return env


def run(cmd: list[str], env: dict[str, str], cwd: Path = ROOT) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for PyO3")
    parser.add_argument("--skip-tests", action="store_true", help="skip cargo test")
    args = parser.parse_args()

    env = clean_env()
    env["PYO3_PYTHON"] = args.python
    cargo = find_cargo()
    env["PATH"] = str(Path(cargo).parent) + os.pathsep + env.get("PATH", "")

    if not args.skip_tests:
        run([cargo, "test", "--workspace"], env)

    run(
        [
            cargo,
            "build",
            "--manifest-path",
            "crates/dual6-py/Cargo.toml",
            "--release",
        ],
        env,
    )

    candidates = [
        ROOT / "target" / "release" / "_native.dll",
        ROOT / "crates" / "dual6-py" / "target" / "release" / "_native.dll",
        ROOT / "target" / "release" / "lib_native.so",
        ROOT / "target" / "release" / "lib_native.dylib",
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        raise SystemExit("native artifact not found after build")

    suffix = ".pyd" if os.name == "nt" else (".dylib" if sys.platform == "darwin" else ".so")
    dest = PYTHON_PKG / f"_native{suffix}"
    shutil.copy2(src, dest)
    print(f"copied {src} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
