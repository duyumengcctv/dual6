"""Microbenchmark the decode paths used by the X/S data models.

The raw scorecard has no X (exact-dual) or S (shadow-projection) codec. This
script measures the concrete operations those models use, for both the pure
Python reference and the optional Rust extension.

Run once per backend and upsert into the CSV:

    python tools/bench_xs.py --measure --backend ref
    python tools/bench_xs.py --measure --backend native
    python tools/bench_xs.py --check-csv

The backend must be chosen before importing ``dual6``; the script sets
``DUAL6_BACKEND`` in ``measure`` and imports there.
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time
from typing import Callable, Dict, List, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "python") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "python"))

BENCH = os.path.join(ROOT, "benchmarks")
DEFAULT_OUT = os.path.join(BENCH, "xs_decode.csv")

FIELDS = (
    "case",
    "data_model",
    "view",
    "implementation",
    "elements",
    "repeats",
    "trials",
    "ns_per_element",
    "backend",
    "method",
    "notes",
)
CASES = {
    "digit_decode",
    "I_bit_channel",
    "I_trit_channel",
    "I_dual_plane_full",
    "X_demux",
    "X_binary_view",
    "X_ternary_view",
    "S_trit_plus_bit",
}


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def _read(path: str) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path: str, rows: Sequence[Dict[str, object]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(v) if isinstance(v, float) else v for k, v in row.items()})


def _min_ns(fn: Callable[[], object], elements: int, repeats: int, trials: int = 5) -> float:
    fn()  # warm-up
    samples = []
    for _ in range(trials):
        start = time.perf_counter()
        for _ in range(repeats):
            fn()
        samples.append((time.perf_counter() - start) / repeats / elements * 1e9)
    return min(samples)


def measure(backend: str) -> List[Dict[str, object]]:
    os.environ["DUAL6_BACKEND"] = backend
    import dual6
    from dual6 import exact_dual

    if dual6.__backend__ != backend:
        raise SystemExit(f"requested {backend}, got {dual6.__backend__}")

    rng = random.Random(2026)
    value = rng.getrandbits(64)
    symbols = exact_dual.encode_number(value)
    width = len(symbols)

    n = 65536
    bits = [rng.randrange(2) for _ in range(n)]
    trits = [rng.choice((-1, 0, 1)) for _ in range(n)]
    bit_bytes = dual6.pack_bits_bytes(bits)
    trit_bytes = dual6.pack_trits_bytes(trits)
    frame = dual6.pack_dual_plane_v2(bits, trits)

    def trit_plus_bit() -> list:
        got = dual6.unpack_trits_bytes(trit_bytes, n)
        return [1 if t else 0 for t in got]

    cases = (
        ("digit_decode", "T", "symbol", "[dual6.decode_digit(d) for d in symbols]", width, 20000,
         "one 6-state symbol arithmetic step per element"),
        ("I_bit_channel", "I", "bit", "dual6.unpack_bits_bytes(bit_bytes, n)", n, 50,
         "LUT unpack of one bit plane"),
        ("I_trit_channel", "I", "trit", "dual6.unpack_trits_bytes(trit_bytes, n)", n, 50,
         "LUT unpack of one trit plane"),
        ("I_dual_plane_full", "I", "both", "dual6.unpack_dual_plane_v2(frame)", n, 20,
         "full D6P2 dual-plane decode"),
        ("X_demux", "X", "both", "dual6.demux(symbols)", width, 20000,
         "batch demux of the exact-dual symbol stream"),
        ("X_binary_view", "X", "bit", "exact_dual.read_binary(symbols)", width, 20000,
         "Python exact-dual binary view"),
        ("X_ternary_view", "X", "trit", "exact_dual.read_ternary(symbols)", width, 20000,
         "Python exact-dual ternary view"),
        ("S_trit_plus_bit", "S", "trit+derived bit", "unpack_trits_bytes + [t != 0]", n, 50,
         "trit unpack plus derived bit"),
    )

    functions = {
        "digit_decode": lambda: [dual6.decode_digit(d) for d in symbols],
        "I_bit_channel": lambda: dual6.unpack_bits_bytes(bit_bytes, n),
        "I_trit_channel": lambda: dual6.unpack_trits_bytes(trit_bytes, n),
        "I_dual_plane_full": lambda: dual6.unpack_dual_plane_v2(frame),
        "X_demux": lambda: dual6.demux(symbols),
        "X_binary_view": lambda: exact_dual.read_binary(symbols),
        "X_ternary_view": lambda: exact_dual.read_ternary(symbols),
        "S_trit_plus_bit": trit_plus_bit,
    }

    rows: List[Dict[str, object]] = []
    for case, model, view, implementation, elements, repeats, note in cases:
        ns = _min_ns(functions[case], elements, repeats)
        rows.append(
            {
                "case": case,
                "data_model": model,
                "view": view,
                "implementation": implementation,
                "elements": elements,
                "repeats": repeats,
                "trials": 5,
                "ns_per_element": ns,
                "backend": backend,
                "method": "raw min-of-5 batches; no loop-baseline subtraction",
                "notes": note,
            }
        )
    return rows


def validate(rows: Sequence[Dict[str, str]]) -> List[str]:
    problems: List[str] = []
    present = {(r.get("backend"), r.get("case")) for r in rows}
    for backend in ("ref", "native"):
        for case in CASES:
            if (backend, case) not in present:
                problems.append(f"missing row: backend={backend} case={case}")
    for row in rows:
        try:
            elements = int(row["elements"])
            ns = float(row["ns_per_element"])
            trials = int(row["trials"])
        except (KeyError, ValueError) as exc:
            problems.append(f"{row.get('backend')}/{row.get('case')}: bad numeric value: {exc}")
            continue
        if elements <= 0 or ns <= 0 or trials < 5:
            problems.append(f"{row['backend']}/{row['case']}: non-positive value or fewer than 5 trials")
    return problems


def check_csv(path: str) -> int:
    rows = _read(path)
    problems = validate(rows)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    for row in rows:
        print(f"ok: {row['backend']:6} {row['case']:20} {row['ns_per_element']} ns/element")
    return 0


def upsert(path: str, rows: Sequence[Dict[str, object]]) -> None:
    existing = _read(path) if os.path.exists(path) else []
    keyed = {(r["backend"], r["case"]): r for r in existing}
    for row in rows:
        keyed[(str(row["backend"]), str(row["case"]))] = {
            k: (_fmt(v) if isinstance(v, float) else str(v)) for k, v in row.items()
        }
    ordered = sorted(keyed.values(), key=lambda r: (r["backend"], r["case"]))
    _write(path, ordered)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", action="store_true", help="run the microbench and upsert the CSV")
    parser.add_argument("--check-csv", action="store_true", help="validate the committed CSV only")
    parser.add_argument("--backend", choices=("ref", "native"), default="ref")
    parser.add_argument("--output", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if args.check_csv:
        return check_csv(args.output)
    if not args.measure:
        raise SystemExit("pass --measure or --check-csv")
    rows = measure(args.backend)
    upsert(args.output, rows)
    print(f"upserted {args.output}: {args.backend}")
    for row in rows:
        print(f"{row['case']:20} {row['ns_per_element']:.2f} ns/element")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
