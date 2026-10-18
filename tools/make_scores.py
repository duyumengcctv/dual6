"""Derive the two scorecard models from ``scorecard_raw.csv``.

The raw battery (``benchmarks/scorecard_raw.csv``) only contains measurements.
This script turns them into the two derived tables used by the README:

* ``benchmarks/scenario_scores.csv`` -- five explicit weight sets over the nine
  metrics, with every sub-score exported so anyone can re-weight;
* ``benchmarks/bandwidth_sweep.csv`` -- the weight-free physical model
  ``effective_ns = max(decode_compute_ns, bytes_per_element / bandwidth)``
  over seven bandwidth levels.

The scenario *weights* are policy, not measurement, and live in the hand-written
``benchmarks/scenario_weights.csv``.  Everything else is generated.

Usage
-----
    python tools/make_scores.py
    python tools/make_scores.py --check
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from typing import Dict, List, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "benchmarks")

SCORECARD = os.path.join(BENCH, "scorecard_raw.csv")
WEIGHTS = os.path.join(BENCH, "scenario_weights.csv")
SCENARIO_OUT = os.path.join(BENCH, "scenario_scores.csv")
BANDWIDTH_OUT = os.path.join(BENCH, "bandwidth_sweep.csv")

PAYLOADS = ("trit", "dual")

# The nine scorecard metrics.  Seven are lower-is-better; the two binary
# structural flags are higher-is-better (1 beats 0).
LOWER_IS_BETTER = (
    "bits_per_element",
    "encode_ns_per_element",
    "decode_ns_net",
    "random_ns_net",
    "sparse_ns_net",
    "selective_bytes",
    "ops_per_element",
)
HIGHER_IS_BETTER = ("integrity", "single_object")
# Output order matches the hand-written weight table: structural flags before
# the complexity proxy.
OUTPUT_METRICS = LOWER_IS_BETTER[:6] + HIGHER_IS_BETTER + ("ops_per_element",)
METRICS = OUTPUT_METRICS

BANDWIDTH_GBPS = (1, 3, 10, 30, 100, 300, 1000)

SCENARIO_FIELDS = (
    "scenario",
    "payload",
    "encoding",
    *[f"score_{m}" for m in OUTPUT_METRICS],
    "weighted_score",
    "rank",
)
BANDWIDTH_FIELDS = (
    "payload",
    "encoding",
    "bandwidth_gbps",
    "bits_per_element",
    "bytes_per_element",
    "decode_compute_ns",
    "memory_ns",
    "effective_ns",
    "dominant",
    "rank",
)


def _read(name: str) -> List[Dict[str, str]]:
    with open(name, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _fmt(value: float) -> str:
    """Stable, compact decimal representation for generated CSVs."""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def _render(rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _fmt(v) if isinstance(v, float) else v for k, v in row.items()})
    return buf.getvalue()


def load_scorecard() -> List[Dict[str, str]]:
    rows = _read(SCORECARD)
    if not rows:
        raise SystemExit(f"{SCORECARD} is empty")
    for row in rows:
        if row["payload"] not in PAYLOADS:
            raise SystemExit(f"unknown payload {row['payload']!r} in {SCORECARD}")
        for metric in METRICS:
            if metric not in row:
                raise SystemExit(f"missing column {metric!r} in {SCORECARD}")
    return rows


def load_weights() -> List[Dict[str, object]]:
    rows = _read(WEIGHTS)
    if not rows:
        raise SystemExit(f"{WEIGHTS} is empty")
    seen = set()
    parsed: List[Dict[str, object]] = []
    for row in rows:
        scenario = row["scenario"]
        if scenario in seen:
            raise SystemExit(f"duplicate scenario {scenario!r} in {WEIGHTS}")
        seen.add(scenario)
        if row["payload"] not in PAYLOADS + ("both",):
            raise SystemExit(f"bad payload {row['payload']!r} for scenario {scenario!r}")
        try:
            weights = {m: int(row[m]) for m in METRICS}
        except (KeyError, ValueError) as exc:
            raise SystemExit(f"bad weight row for scenario {scenario!r}: {exc}") from exc
        if any(w < 0 for w in weights.values()):
            raise SystemExit(f"negative weight in scenario {scenario!r}")
        if sum(weights.values()) != 100:
            raise SystemExit(
                f"weights for scenario {scenario!r} sum to {sum(weights.values())}, expected 100"
            )
        parsed.append(
            {
                "scenario": scenario,
                "payload": row["payload"],
                "description": row["description"],
                "weights": weights,
            }
        )
    return parsed


def _ranks(values: Sequence[float], reverse: bool) -> List[int]:
    """Standard competition ranking (1, 2, 2, 4)."""
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=reverse)
    ranks = [0] * len(values)
    previous: float | None = None
    previous_rank = 0
    for position, index in enumerate(order, start=1):
        value = values[index]
        if previous is not None and abs(value - previous) < 1e-12:
            ranks[index] = previous_rank
        else:
            ranks[index] = position
            previous_rank = position
        previous = value
    return ranks


def scenario_scores(
    scorecard: Sequence[Dict[str, str]], scenarios: Sequence[Dict[str, object]]
) -> List[Dict[str, object]]:
    by_payload = {p: [r for r in scorecard if r["payload"] == p] for p in PAYLOADS}
    out: List[Dict[str, object]] = []
    for scenario in scenarios:
        scope = str(scenario["payload"])
        weights = scenario["weights"]
        if not isinstance(weights, dict):
            raise SystemExit(f"bad parsed weights for scenario {scenario['scenario']!r}")
        for payload in PAYLOADS:
            if scope != "both" and scope != payload:
                continue
            group = by_payload[payload]
            best_values = {
                metric: min(float(r[metric]) for r in group)
                for metric in LOWER_IS_BETTER
            }
            rows: List[Dict[str, object]] = []
            for row in group:
                sub: Dict[str, float] = {}
                for metric in LOWER_IS_BETTER:
                    value = float(row[metric])
                    if value <= 0:
                        raise SystemExit(f"non-positive {metric} for {row['encoding']!r}")
                    sub[metric] = best_values[metric] / value
                for metric in HIGHER_IS_BETTER:
                    value = float(row[metric])
                    if value not in (0.0, 1.0):
                        raise SystemExit(f"{metric} for {row['encoding']!r} must be 0 or 1")
                    sub[metric] = value
                weighted = sum(weights[m] / 100.0 * sub[m] for m in METRICS) * 100.0
                entry: Dict[str, object] = {
                    "scenario": scenario["scenario"],
                    "payload": payload,
                    "encoding": row["encoding"],
                    "weighted_score": weighted,
                }
                entry.update({f"score_{m}": sub[m] for m in METRICS})
                rows.append(entry)
            ranks = _ranks([float(r["weighted_score"]) for r in rows], reverse=True)
            for entry, rank in zip(rows, ranks):
                entry["rank"] = rank
            rows.sort(key=lambda r: (int(r["rank"]), str(r["encoding"])))
            out.extend(rows)
    return out


def bandwidth_sweep(scorecard: Sequence[Dict[str, str]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for payload in PAYLOADS:
        group = [r for r in scorecard if r["payload"] == payload]
        for bandwidth in BANDWIDTH_GBPS:
            rows: List[Dict[str, object]] = []
            for row in group:
                bits = float(row["bits_per_element"])
                bytes_per_element = bits / 8.0
                compute = float(row["decode_ns_native"])
                memory = bytes_per_element / bandwidth
                effective = max(compute, memory)
                rows.append(
                    {
                        "payload": payload,
                        "encoding": row["encoding"],
                        "bandwidth_gbps": bandwidth,
                        "bits_per_element": bits,
                        "bytes_per_element": bytes_per_element,
                        "decode_compute_ns": compute,
                        "memory_ns": memory,
                        "effective_ns": effective,
                        "dominant": "compute" if compute >= memory else "memory",
                    }
                )
            ranks = _ranks([float(r["effective_ns"]) for r in rows], reverse=False)
            for entry, rank in zip(rows, ranks):
                entry["rank"] = rank
            rows.sort(key=lambda r: (int(r["rank"]), str(r["encoding"])))
            out.extend(rows)
    return out


def render_all() -> Dict[str, str]:
    scorecard = load_scorecard()
    scenarios = load_weights()
    return {
        SCENARIO_OUT: _render(scenario_scores(scorecard, scenarios), SCENARIO_FIELDS),
        BANDWIDTH_OUT: _render(bandwidth_sweep(scorecard), BANDWIDTH_FIELDS),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that the committed derived CSVs match a fresh computation",
    )
    args = parser.parse_args(argv)

    rendered = render_all()
    problems = []
    for path, text in rendered.items():
        if args.check:
            if not os.path.exists(path):
                problems.append(f"{path}: missing")
                continue
            with open(path, encoding="utf-8", newline="") as fh:
                current = fh.read()
            if current != text:
                problems.append(f"{path}: stale (run python tools/make_scores.py)")
            else:
                print(f"ok: {path}")
        else:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            print(f"wrote {path}")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
