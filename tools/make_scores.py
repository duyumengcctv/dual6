"""Derive the scorecard tables from the raw measurements.

The raw battery (``benchmarks/scorecard_raw.csv``) only contains measurements.
This script turns them into the derived tables used by the README:

* ``benchmarks/scenario_scores.csv`` -- five explicit weight sets over the nine
  metrics, with every sub-score exported so anyone can re-weight;
* ``benchmarks/bandwidth_sweep.csv`` -- the weight-free physical model
  ``effective_ns = max(decode_compute_ns, bytes_per_element / bandwidth)``
  over seven bandwidth levels;
* ``benchmarks/composite_scores.csv`` -- equal-weight comprehensive score per
  encoding (nine measured sub-scores plus information utilization), tagged with
  its data model;
* ``benchmarks/xs_scores.csv`` -- the same ten-metric score for X and S, using
  measured decode timings from ``benchmarks/xs_decode.csv`` and dual-plane
  proxies for the remaining timing metrics;
* ``benchmarks/information_budget.csv`` -- information vs storage bits for the
  T / I / X / S data models (the conceptual distinction behind the scorecard);
* ``benchmarks/decode_ratios.csv`` -- raw/net/native decode ratios against a
  payload-specific reference, including the clamped-net flag;
* ``benchmarks/weight_sensitivity.csv`` -- win shares under deterministic
  pseudo-random simplex weight draws;
* ``benchmarks/weight_sweeps.csv`` -- one-dimensional weight sweeps that show
  where the winner flips.

The scenario *weights* are policy, not measurement, and live in the hand-written
``benchmarks/scenario_weights.csv``.  The per-channel layout facts live in
``benchmarks/encoding_layout.csv``.  Everything else is generated.

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
from typing import Dict, List, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "benchmarks")

SCORECARD = os.path.join(BENCH, "scorecard_raw.csv")
LAYOUT = os.path.join(BENCH, "encoding_layout.csv")
DATA_MODELS = os.path.join(BENCH, "data_models.csv")
XS_DECODE = os.path.join(BENCH, "xs_decode.csv")
TAXONOMY = os.path.join(BENCH, "encoding_taxonomy.csv")
WEIGHTS = os.path.join(BENCH, "scenario_weights.csv")
SCENARIO_OUT = os.path.join(BENCH, "scenario_scores.csv")
BANDWIDTH_OUT = os.path.join(BENCH, "bandwidth_sweep.csv")
COMPOSITE_OUT = os.path.join(BENCH, "composite_scores.csv")
XS_OUT = os.path.join(BENCH, "xs_scores.csv")
INFORMATION_OUT = os.path.join(BENCH, "information_budget.csv")
DECODE_OUT = os.path.join(BENCH, "decode_ratios.csv")
SENSITIVITY_OUT = os.path.join(BENCH, "weight_sensitivity.csv")
SWEEPS_OUT = os.path.join(BENCH, "weight_sweeps.csv")

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
COMPOSITE_METRICS = METRICS + ("information_utilization",)

BANDWIDTH_GBPS = (1, 3, 10, 30, 100, 300, 1000)
SCHEMES = (("s1", 2026), ("s2", 2027), ("s3", 2028))
RANDOM_DRAWS = 5000
SWEEP_STEP = 5
REFERENCE = {
    "trit": "Dual6 dual-plane (trit-only frame)",
    "dual": "Dual6 dual-plane",
}

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
COMPOSITE_FIELDS = (
    "payload",
    "data_model",
    "encoding",
    "evidence",
    "decode_backend",
    "proxy_source",
    "info_bits_per_element",
    "storage_bits_per_element",
    "utilization_pct",
    "redundancy_ratio",
    *[f"score_{m}" for m in OUTPUT_METRICS],
    "score_information_utilization",
    "composite_score",
    "rank",
)
INFORMATION_FIELDS = (
    "data_model",
    "name",
    "meaning",
    "info_bits_per_element",
    "dual6_storage_bits_per_element",
    "utilization_pct",
    "redundancy_ratio",
    "interconvertible",
    "write_semantics",
    "notes",
)
DECODE_FIELDS = (
    "payload",
    "encoding",
    "reference",
    "decode_ns_per_element",
    "decode_ns_net",
    "decode_ns_native",
    "compute_source",
    "decode_net_clamped",
    "ratio_raw_vs_reference",
    "ratio_net_vs_reference",
    "ratio_native_vs_reference",
)
SENSITIVITY_FIELDS = (
    "analysis",
    "payload",
    "scheme",
    "draws",
    "encoding",
    "wins",
    "share",
)
SWEEP_FIELDS = ("analysis", "payload", "parameter", "encoding", "score")


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


def load_layout(scorecard: Sequence[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, str]]:
    rows = _read(LAYOUT)
    if not rows:
        raise SystemExit(f"{LAYOUT} is empty")
    raw = {(r["encoding"], r["payload"]): r for r in scorecard}
    layout: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in rows:
        key = (row["encoding"], row["payload"])
        if key not in raw:
            raise SystemExit(f"layout row {key!r} has no scorecard row")
        if int(row["payload_bytes"]) != int(raw[key]["bytes_total"]):
            raise SystemExit(
                f"layout payload_bytes {row['payload_bytes']} != scorecard bytes_total "
                f"{raw[key]['bytes_total']} for {key!r}"
            )
        bit = int(row["bit_plane_bytes"])
        trit = int(row["trit_plane_bytes"])
        worst = int(row["selective_bytes_worst"])
        if worst != max(bit, trit):
            raise SystemExit(f"selective_bytes_worst must be max(bit, trit) for {key!r}")
        layout[key] = row
    if set(layout) != set(raw):
        missing = sorted(set(raw) - set(layout))
        extra = sorted(set(layout) - set(raw))
        raise SystemExit(f"layout/scorecard mismatch: missing={missing} extra={extra}")
    return layout


def load_taxonomy() -> Dict[Tuple[str, str], Dict[str, str]]:
    rows = _read(TAXONOMY)
    taxonomy: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in rows:
        taxonomy[(row["encoding"], row["payload"])] = row
    return taxonomy


def information_budget() -> List[Dict[str, object]]:
    rows = _read(DATA_MODELS)
    out: List[Dict[str, object]] = []
    for row in rows:
        info = float(row["info_bits_per_element"])
        storage = float(row["dual6_storage_bits_per_element"])
        out.append(
            {
                "data_model": row["data_model"],
                "name": row["name"],
                "meaning": row["meaning"],
                "info_bits_per_element": info,
                "dual6_storage_bits_per_element": storage,
                "utilization_pct": info / storage * 100.0,
                "redundancy_ratio": storage / info,
                "interconvertible": row["interconvertible"],
                "write_semantics": row["write_semantics"],
                "notes": row["notes"],
            }
        )
    return out


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


def _metric_value(
    row: Dict[str, str], metric: str, layout: Dict[Tuple[str, str], Dict[str, str]]
) -> float:
    if metric == "selective_bytes":
        return float(layout[(row["encoding"], row["payload"])]["selective_bytes_worst"])
    return float(row[metric])


def _subscores(
    group: Sequence[Dict[str, str]], layout: Dict[Tuple[str, str], Dict[str, str]]
) -> Dict[str, Dict[str, float]]:
    best = {
        metric: min(_metric_value(r, metric, layout) for r in group)
        for metric in LOWER_IS_BETTER
    }
    out: Dict[str, Dict[str, float]] = {}
    for row in group:
        sub: Dict[str, float] = {}
        for metric in LOWER_IS_BETTER:
            value = _metric_value(row, metric, layout)
            if value <= 0:
                raise SystemExit(f"non-positive {metric} for {row['encoding']!r}")
            sub[metric] = best[metric] / value
        for metric in HIGHER_IS_BETTER:
            sub[metric] = _metric_value(row, metric, layout)
        out[row["encoding"]] = sub
    return out


def _weighted(sub: Dict[str, float], weights: Dict[str, float]) -> float:
    return sum(weights[m] / 100.0 * sub[m] for m in METRICS) * 100.0


def scenario_scores(
    scorecard: Sequence[Dict[str, str]],
    scenarios: Sequence[Dict[str, object]],
    layout: Dict[Tuple[str, str], Dict[str, str]],
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
            subs = _subscores(group, layout)
            rows: List[Dict[str, object]] = []
            for row in group:
                entry: Dict[str, object] = {
                    "scenario": scenario["scenario"],
                    "payload": payload,
                    "encoding": row["encoding"],
                    "weighted_score": _weighted(subs[row["encoding"]], weights),
                }
                entry.update({f"score_{m}": subs[row["encoding"]][m] for m in METRICS})
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


def composite_scores(
    scorecard: Sequence[Dict[str, str]],
    layout: Dict[Tuple[str, str], Dict[str, str]],
    taxonomy: Dict[Tuple[str, str], Dict[str, str]],
) -> List[Dict[str, object]]:
    """Ten-metric score for the measured T/I rows."""
    out: List[Dict[str, object]] = []
    for payload in PAYLOADS:
        group = [r for r in scorecard if r["payload"] == payload]
        subs = _subscores(group, layout)
        rows: List[Dict[str, object]] = []
        for encoding, sub in subs.items():
            tax = taxonomy[(encoding, payload)]
            info = float(tax["info_bits_per_element"])
            storage = float(tax["storage_bits_per_element"])
            utilization = info / storage
            entry: Dict[str, object] = {
                "payload": payload,
                "data_model": tax["data_model"],
                "encoding": encoding,
                "evidence": "measured",
                "decode_backend": "python_net",
                "proxy_source": "",
                "info_bits_per_element": info,
                "storage_bits_per_element": storage,
                "utilization_pct": utilization * 100.0,
                "redundancy_ratio": storage / info,
                "score_information_utilization": utilization,
                "composite_score": (
                    sum(sub[m] for m in METRICS) + utilization
                )
                / len(COMPOSITE_METRICS)
                * 100.0,
            }
            entry.update({f"score_{m}": sub[m] for m in METRICS})
            rows.append(entry)
        ranks = _ranks([float(r["composite_score"]) for r in rows], reverse=True)
        for entry, rank in zip(rows, ranks):
            entry["rank"] = rank
        rows.sort(key=lambda r: (int(r["rank"]), str(r["encoding"])))
        out.extend(rows)
    return out


def xs_scores(
    scorecard: Sequence[Dict[str, str]],
    layout: Dict[Tuple[str, str], Dict[str, str]],
    taxonomy: Dict[Tuple[str, str], Dict[str, str]],
) -> List[Dict[str, object]]:
    """X/S rows: decode is measured, other timing metrics are dual-plane proxies."""
    models = {r["data_model"]: r for r in _read(DATA_MODELS)}
    decode_rows = _read(XS_DECODE)
    decode = {
        (r["backend"], r["case"]): float(r["ns_per_element"]) for r in decode_rows
    }
    group = [r for r in scorecard if r["payload"] == "dual"]
    proxy = next(r for r in group if r["encoding"] == "Dual6 dual-plane")
    proxy_values = {
        "bits_per_element": 2.6,
        "encode_ns_per_element": float(proxy["encode_ns_per_element"]),
        "random_ns_net": float(proxy["random_ns_net"]),
        "sparse_ns_net": float(proxy["sparse_ns_net"]),
        "selective_bytes": float(
            layout[("Dual6 dual-plane", "dual")]["selective_bytes_worst"]
        ),
        "ops_per_element": 4.0,
    }
    best = {
        metric: min(_metric_value(r, metric, layout) for r in group)
        for metric in LOWER_IS_BETTER
    }
    rows: List[Dict[str, object]] = []
    for model, decode_case in (
        ("X", "X_binary_view"),
        ("S", "S_trit_plus_bit"),
    ):
        source = models[model]
        info = float(source["info_bits_per_element"])
        storage = float(source["dual6_storage_bits_per_element"])
        utilization = info / storage
        values = dict(proxy_values)
        if model == "X":
            values["decode_ns_net"] = decode[("native", "X_demux")]
        else:
            values["decode_ns_net"] = decode[("native", "S_trit_plus_bit")]
        sub: Dict[str, float] = {}
        for metric in LOWER_IS_BETTER:
            sub[metric] = best[metric] / values[metric]
        for metric in HIGHER_IS_BETTER:
            sub[metric] = 1.0
        entry: Dict[str, object] = {
            "payload": "dual",
            "data_model": model,
            "encoding": f"Dual6/{model} ({source['name']})",
            "evidence": "mixed_native_decode",
            "decode_backend": "native_batch",
            "proxy_source": "decode: xs_decode.csv (native batch); other timing: Dual6 dual-plane / dual",
            "info_bits_per_element": info,
            "storage_bits_per_element": storage,
            "utilization_pct": utilization * 100.0,
            "redundancy_ratio": storage / info,
            "score_information_utilization": utilization,
            "composite_score": (
                sum(sub[m] for m in METRICS) + utilization
            )
            / len(COMPOSITE_METRICS)
            * 100.0,
        }
        entry.update({f"score_{m}": sub[m] for m in METRICS})
        rows.append(entry)
    ranks = _ranks([float(r["composite_score"]) for r in rows], reverse=True)
    for entry, rank in zip(rows, ranks):
        entry["rank"] = rank
    rows.sort(key=lambda r: (int(r["rank"]), str(r["encoding"])))
    return rows


def decode_ratios(scorecard: Sequence[Dict[str, str]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for payload in PAYLOADS:
        group = [r for r in scorecard if r["payload"] == payload]
        reference_name = REFERENCE[payload]
        reference = next(r for r in group if r["encoding"] == reference_name)
        reference_raw = float(reference["decode_ns_per_element"])
        reference_net = float(reference["decode_ns_net"])
        reference_native = float(reference["decode_ns_native"])
        for row in group:
            raw = float(row["decode_ns_per_element"])
            net = float(row["decode_ns_net"])
            native = float(row["decode_ns_native"])
            loop = float(row["py_loop_overhead_ns"])
            out.append(
                {
                    "payload": payload,
                    "encoding": row["encoding"],
                    "reference": reference_name,
                    "decode_ns_per_element": raw,
                    "decode_ns_net": net,
                    "decode_ns_native": native,
                    "compute_source": row["compute_source"],
                    "decode_net_clamped": 1 if raw - loop < 0 else 0,
                    "ratio_raw_vs_reference": reference_raw / raw,
                    "ratio_net_vs_reference": reference_net / net,
                    "ratio_native_vs_reference": reference_native / native,
                }
            )
    return out


_MASK64 = (1 << 64) - 1


class _DetRng:
    """SplitMix64; deterministic across Python versions."""

    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK64

    def u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return z ^ (z >> 31)

    def uniform(self) -> float:
        return (self.u64() >> 11) / float(1 << 53)


def _random_weights(rng: _DetRng) -> Dict[str, int]:
    """A deterministic integer weight vector that sums to 100.

    Integer arithmetic only: no transcendental functions, so the generated CSV
    is stable across operating systems and Python versions.
    """
    raw = [1 + rng.u64() % 1000 for _ in METRICS]
    total = sum(raw)
    scaled = [value * 100 for value in raw]
    weights = [value // total for value in scaled]
    remainder = 100 - sum(weights)
    order = sorted(range(len(raw)), key=lambda i: (-(scaled[i] % total), i))
    for index in order[:remainder]:
        weights[index] += 1
    return dict(zip(METRICS, weights))


def weight_sensitivity(
    scorecard: Sequence[Dict[str, str]],
    layout: Dict[Tuple[str, str], Dict[str, str]],
) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for payload in PAYLOADS:
        group = [r for r in scorecard if r["payload"] == payload]
        subs = _subscores(group, layout)
        for scheme, seed in SCHEMES:
            rng = _DetRng(seed + (0 if payload == "trit" else 1000))
            wins = {encoding: 0 for encoding in subs}
            for _ in range(RANDOM_DRAWS):
                weights = _random_weights(rng)
                winner = max(
                    subs, key=lambda e: sum(weights[m] * subs[e][m] for m in METRICS)
                )
                wins[winner] += 1
            for encoding in sorted(wins, key=lambda e: (-wins[e], e)):
                out.append(
                    {
                        "analysis": "random_simplex",
                        "payload": payload,
                        "scheme": scheme,
                        "draws": RANDOM_DRAWS,
                        "encoding": encoding,
                        "wins": wins[encoding],
                        "share": wins[encoding] / RANDOM_DRAWS,
                    }
                )
    return out


def weight_sweeps(
    scorecard: Sequence[Dict[str, str]],
    layout: Dict[Tuple[str, str], Dict[str, str]],
) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for payload in PAYLOADS:
        group = [r for r in scorecard if r["payload"] == payload]
        subs = _subscores(group, layout)
        for analysis in ("structural", "storage", "selective"):
            if analysis == "selective" and payload != "dual":
                continue
            for parameter in range(0, 101, SWEEP_STEP):
                if analysis == "structural":
                    weights = {
                        m: (100.0 - parameter) / len(LOWER_IS_BETTER)
                        for m in LOWER_IS_BETTER
                    }
                    weights["integrity"] = parameter / 2.0
                    weights["single_object"] = parameter / 2.0
                else:
                    target = (
                        "bits_per_element" if analysis == "storage" else "selective_bytes"
                    )
                    weights = {
                        m: (100.0 - parameter) / (len(METRICS) - 1)
                        for m in METRICS
                        if m != target
                    }
                    weights[target] = float(parameter)
                for encoding in subs:
                    out.append(
                        {
                            "analysis": analysis,
                            "payload": payload,
                            "parameter": parameter,
                            "encoding": encoding,
                            "score": _weighted(subs[encoding], weights),
                        }
                    )
    return out


def render_all() -> Dict[str, str]:
    scorecard = load_scorecard()
    layout = load_layout(scorecard)
    taxonomy = load_taxonomy()
    scenarios = load_weights()
    return {
        SCENARIO_OUT: _render(scenario_scores(scorecard, scenarios, layout), SCENARIO_FIELDS),
        BANDWIDTH_OUT: _render(bandwidth_sweep(scorecard), BANDWIDTH_FIELDS),
        COMPOSITE_OUT: _render(
            composite_scores(scorecard, layout, taxonomy), COMPOSITE_FIELDS
        ),
        XS_OUT: _render(
            xs_scores(scorecard, layout, taxonomy), COMPOSITE_FIELDS
        ),
        INFORMATION_OUT: _render(information_budget(), INFORMATION_FIELDS),
        DECODE_OUT: _render(decode_ratios(scorecard), DECODE_FIELDS),
        SENSITIVITY_OUT: _render(weight_sensitivity(scorecard, layout), SENSITIVITY_FIELDS),
        SWEEPS_OUT: _render(weight_sweeps(scorecard, layout), SWEEP_FIELDS),
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
