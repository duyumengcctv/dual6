"""Check that Dual6 version strings are consistent across the repo."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def find(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise SystemExit(f"could not find version in {label}")
    return match.group(1)


def main() -> int:
    cargo = read("Cargo.toml")
    workspace_section = cargo.split("[workspace.package]", 1)[1]
    versions = {
        "python/dual6/__init__.py": find(
            r'__version__\s*=\s*"([^"]+)"',
            read("python/dual6/__init__.py"),
            "python/dual6/__init__.py",
        ),
        "pyproject.toml": find(
            r'^version\s*=\s*"([^"]+)"',
            read("pyproject.toml"),
            "pyproject.toml",
        ),
        "Cargo.toml[workspace.package]": find(
            r'^version\s*=\s*"([^"]+)"',
            workspace_section,
            "Cargo.toml[workspace.package]",
        ),
        "crates/dual6-py/Cargo.toml": find(
            r'^version\s*=\s*"([^"]+)"',
            read("crates/dual6-py/Cargo.toml"),
            "crates/dual6-py/Cargo.toml",
        ),
    }

    unique = set(versions.values())
    if len(unique) != 1:
        print("version mismatch:")
        for path, version in versions.items():
            print(f"  {path}: {version}")
        return 1
    print(f"versions consistent: {unique.pop()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
