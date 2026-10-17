"""Report and check native (PyO3) API coverage for Dual6.

Two numbers are tracked:

* **total callables** -- every public callable the ``dual6`` package may expose
  across both backends.  Some of these belong to the Python object model and
  intentionally stay in ``_ref`` (see ``REF_ONLY_BY_DESIGN``).
* **native-eligible** -- public callables whose behaviour is pure data
  marshalling and can therefore be implemented in Rust.  This set must stay
  100% native-backed; otherwise a function silently regressed to Python.

Exit status is non-zero when the stub file and the Rust module disagree, when an
eligible callable is not native, or when the allow-list is stale.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST_SRC = ROOT / "crates" / "dual6-py" / "src" / "lib.rs"
STUB = ROOT / "python" / "dual6" / "_native.pyi"

# Public callables that stay in the reference layer on purpose.  Updating this
# map is a deliberate API decision, not an accident.
REF_ONLY_BY_DESIGN: dict[str, str] = {
    # Python object model -------------------------------------------------
    "BitView": "object-model: Python Sequence view class",
    "TritView": "object-model: Python Sequence view class",
    "BlockLayout": "object-model: frozen dataclass",
    "DualPlaneBlockLayout": "object-model: frozen dataclass",
    "Dual6Error": "object-model: exception type",
    "ErrorCode": "object-model: enum type",
    "MappedFrame": "object-model: context manager",
    # Layout objects are Python dataclasses; the native core works on raw widths.
    "get_layout": "layout-object: returns BlockLayout",
    "get_dp_layout": "layout-object: returns DualPlaneBlockLayout",
    "pack_block": "layout-object: takes BlockLayout",
    "unpack_block": "layout-object: takes BlockLayout",
    "pack_block_dp": "layout-object: takes DualPlaneBlockLayout",
    "unpack_block_dp": "layout-object: takes DualPlaneBlockLayout",
    # View factories return the Python view classes above.
    "bit_view": "view-factory: returns BitView",
    "trit_view": "view-factory: returns TritView",
    # Filesystem / mmap boundary.
    "read_frame": "file-io: filesystem boundary",
    "write_frame": "file-io: filesystem boundary",
    "main_check": "file-io: filesystem boundary",
}


def rust_exports() -> set[str]:
    text = RUST_SRC.read_text(encoding="utf-8")
    return set(re.findall(r"wrap_pyfunction!\(([A-Za-z0-9_]+),\s*m\)", text))


def stub_exports() -> set[str]:
    text = STUB.read_text(encoding="utf-8")
    return set(re.findall(r"^def ([A-Za-z0-9_]+)\(", text, re.M))


def public_callables() -> set[str]:
    sys.path.insert(0, str(ROOT / "python"))
    import dual6

    names = set(dual6.__all__)
    return {name for name in names if callable(getattr(dual6, name, None))}


def analyse() -> dict[str, object]:
    native = rust_exports()
    stub = stub_exports()
    public = public_callables()
    universe = public | native
    ref_only = universe - native
    eligible_missing = sorted(ref_only - set(REF_ONLY_BY_DESIGN))
    stale_allow = sorted(set(REF_ONLY_BY_DESIGN) - ref_only)
    return {
        "native": native,
        "stub": stub,
        "public": public,
        "universe": universe,
        "ref_only": ref_only,
        "eligible_missing": eligible_missing,
        "stale_allow": stale_allow,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit raw numbers as JSON")
    args = parser.parse_args()

    info = analyse()
    native = info["native"]
    stub = info["stub"]
    universe = info["universe"]
    missing = info["eligible_missing"]
    stale = info["stale_allow"]

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "native": len(native),
                    "total_callables": len(universe),
                    "ref_only_by_design": len(info["ref_only"]),
                    "eligible_missing": missing,
                    "stale_allow_list": stale,
                },
                ensure_ascii=False,
            )
        )

    problems: list[str] = []
    if native != stub:
        problems.append(f"stub/rust mismatch: rust-only={sorted(native - stub)} stub-only={sorted(stub - native)}")
    if missing:
        problems.append(f"native-eligible callables missing from Rust: {missing}")
    if stale:
        problems.append(f"REF_ONLY_BY_DESIGN entries that are now native: {stale}")

    print(f"native-backed : {len(native)} / {len(universe)} public callables")
    print(f"native-eligible: {len(universe) - len(info['ref_only'])} / {len(universe) - len(info['ref_only'])}")
    print("ref-only by design:")
    for name in sorted(info["ref_only"]):
        print(f"  - {name:<22} {REF_ONLY_BY_DESIGN.get(name, 'MISSING REASON')}")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("OK: native coverage consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
