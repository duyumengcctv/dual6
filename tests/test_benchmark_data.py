"""The numbers quoted in README/benchmarks must match the CSVs.

`benchmarks/` is data, not decoration: if a CSV is regenerated and a headline
number moves, the README has to move with it or this fails.
"""

from __future__ import annotations

import csv
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "benchmarks")


def rows(name):
    with open(os.path.join(BENCH, name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class DataFiles(unittest.TestCase):
    def test_expected_files_exist(self):
        for name in (
            "scorecard_raw.csv",
            "scenario_weights.csv",
            "encoding_layout.csv",
            "data_models.csv",
            "encoding_taxonomy.csv",
            "scenario_scores.csv",
            "bandwidth_sweep.csv",
            "composite_scores.csv",
            "xs_scores.csv",
            "xs_decode.csv",
            "information_budget.csv",
            "decode_ratios.csv",
            "weight_sensitivity.csv",
            "weight_sweeps.csv",
            "model_roundtrip.csv",
            "sparse_plane.csv",
            "mask_structure.csv",
            "fault_size.csv",
            "fault_matrix.csv",
            "README.md",
        ):
            with self.subTest(file=name):
                self.assertTrue(os.path.exists(os.path.join(BENCH, name)))

    def test_charts_exist(self):
        charts = os.path.join(BENCH, "charts")
        found = sorted(f for f in os.listdir(charts) if f.endswith(".png"))
        self.assertEqual(
            found,
            [
                "bandwidth-crossover.png",
                "composite-scores.png",
                "fault-size.png",
                "information-budget.png",
                "mask-structure.png",
                "scenario-scores.png",
                "scorecard.png",
                "sparse-plane.png",
                "weight-sensitivity.png",
            ],
        )

    def test_every_chart_is_referenced_by_a_readme(self):
        for readme in ("README.md", "README.zh-CN.md"):
            text = read(readme)
            for name in ("scorecard.png", "sparse-plane.png", "mask-structure.png",
                         "fault-size.png", "scenario-scores.png", "bandwidth-crossover.png",
                         "weight-sensitivity.png", "composite-scores.png",
                         "information-budget.png"):
                with self.subTest(readme=readme, chart=name):
                    self.assertIn("benchmarks/charts/" + name, text)


class Scorecard(unittest.TestCase):
    def test_trit_only_frame_matches_tq1_density(self):
        data = {(r["encoding"], r["payload"]): r for r in rows("scorecard_raw.csv")}
        dual6 = data[("Dual6 dual-plane (trit-only frame)", "trit")]
        tq1 = data[("TQ1_0 (5 trit/byte)", "trit")]
        self.assertAlmostEqual(
            float(dual6["bits_per_element"]), float(tq1["bits_per_element"]), places=3
        )
        self.assertLess(float(dual6["bits_per_element"]), 1.61)
        # the README quotes 59.2 ns; keep the doc and the data together
        self.assertAlmostEqual(float(dual6["decode_ns_net"]), 59.2, delta=1.0)


NAME_EN = {
    "TQ1_0": "TQ1_0 (5 trit/byte)",
    "TQ2_0": "TQ2_0 (2 bit/trit)",
    "Dual6 dual-plane (trit-only)": "Dual6 dual-plane (trit-only frame)",
    "Dual6 trit-only": "Dual6 dual-plane (trit-only frame)",
    "Dual6 interleaved (13 bit)": "Dual6 interleaved (13 bit/5 sym)",
    "Dual6 interleaved": "Dual6 interleaved (13 bit/5 sym)",
    "two arrays": "two separate arrays",
    "6-state slot": "6-state 3-bit slot",
}
NAME_ZH = {
    "TQ1_0": "TQ1_0 (5 trit/byte)",
    "TQ2_0": "TQ2_0 (2 bit/trit)",
    "fp16 稠密": "fp16 dense",
    "int8 稠密": "int8 dense",
    "6 态 3-bit 槽": "6-state 3-bit slot",
    "Dual6 双平面": "Dual6 dual-plane",
    "Dual6 双平面（trit-only）": "Dual6 dual-plane (trit-only frame)",
    "Dual6 交错（13 bit）": "Dual6 interleaved (13 bit/5 sym)",
    "两份独立数组": "two separate arrays",
    "Dual6 trit-only": "Dual6 dual-plane (trit-only frame)",
    "Dual6 interleaved": "Dual6 interleaved (13 bit/5 sym)",
    "two arrays": "two separate arrays",
    "6-state slot": "6-state 3-bit slot",
}

LOWER = (
    "bits_per_element",
    "encode_ns_per_element",
    "decode_ns_net",
    "random_ns_net",
    "sparse_ns_net",
    "selective_bytes",
    "ops_per_element",
)
HIGHER = ("integrity", "single_object")
SKIP_FIRST = {
    "Encoding", "encoding", "编码", "Scenario", "场景",
    "Bandwidth (GB/s)", "带宽 (GB/s)", "Rank", "排名", "Model", "模型",
}
# Column order used by the hand-written weights table (same as the CSV).
METRIC_ORDER = LOWER[:6] + HIGHER + ("ops_per_element",)


def _section_rows(text, start, end=None):
    assert start in text, f"missing section marker: {start}"
    chunk = text.split(start, 1)[1]
    if end is not None:
        chunk = chunk.split(end, 1)[0]
    out = []
    for line in chunk.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if cells[0] in SKIP_FIRST:
            continue
        out.append(cells)
    return out


def _name(cells, mapping):
    return mapping.get(cells[0], cells[0])


def _competition_ranks(values, reverse):
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=reverse)
    ranks = [0] * len(values)
    previous = None
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


class ScorecardShape(unittest.TestCase):
    def test_raw_shape_and_payloads(self):
        data = rows("scorecard_raw.csv")
        self.assertEqual(len(data), 15)
        self.assertEqual(len(data[0]), 19)
        self.assertEqual(sum(1 for r in data if r["payload"] == "trit"), 9)
        self.assertEqual(sum(1 for r in data if r["payload"] == "dual"), 6)
        self.assertEqual(len({r["encoding"] for r in data}), 9)


class ScorecardTables(unittest.TestCase):
    """Every rendered scorecard table must match scorecard_raw.csv."""

    def _check_table(self, table_rows, payload, mapping):
        data = {(r["encoding"], r["payload"]): r for r in rows("scorecard_raw.csv")}
        layout = {(r["encoding"], r["payload"]): r for r in rows("encoding_layout.csv")}
        expected = 9 if payload == "trit" else 6
        self.assertEqual(len(table_rows), expected)
        for cells in table_rows:
            name = _name(cells, mapping)
            row = data[(name, payload)]
            lay = layout[(name, payload)]
            with self.subTest(encoding=name, payload=payload):
                self.assertAlmostEqual(float(cells[1]), float(row["bits_per_element"]), places=2)
                self.assertAlmostEqual(float(cells[2]), float(row["encode_ns_per_element"]), delta=0.05)
                self.assertAlmostEqual(float(cells[3]), float(row["decode_ns_net"]), delta=0.05)
                native = cells[4].replace("†", "")
                self.assertAlmostEqual(float(native), float(row["decode_ns_native"]), delta=0.0006)
                self.assertEqual("†" in cells[4], row["compute_source"] == "memcpy_floor")
                self.assertAlmostEqual(float(cells[5]), float(row["random_ns_net"]), delta=0.05)
                self.assertAlmostEqual(float(cells[6]), float(row["sparse_ns_net"]), delta=0.05)
                self.assertEqual(int(cells[7]), int(lay["selective_bytes_bit"]))
                self.assertEqual(int(cells[8]), int(lay["selective_bytes_trit"]))
                self.assertEqual(cells[9] == "✓", row["integrity"] == "1")
                self.assertEqual(cells[10] == "✓", row["single_object"] == "1")

    def test_readme_english_tables(self):
        text = read("README.md")
        self._check_table(
            _section_rows(text, "#### T payload: trit-only", "#### I payload: independent pair"),
            "trit", NAME_EN,
        )
        self._check_table(
            _section_rows(text, "#### I payload: independent pair", "#### Comprehensive score: T and I (equal weights)"),
            "dual", NAME_EN,
        )

    def test_readme_chinese_tables(self):
        text = read("README.zh-CN.md")
        self._check_table(
            _section_rows(text, "#### T 载荷：纯三值", "#### I 载荷：独立双通道"),
            "trit", NAME_ZH,
        )
        self._check_table(
            _section_rows(text, "#### I 载荷：独立双通道", "#### 综合评分：T 与 I（等权）"),
            "dual", NAME_ZH,
        )

    def test_benchmarks_readme_tables(self):
        text = read("benchmarks/README.md")
        self._check_table(
            _section_rows(text, "### Summary — pure-trit payload", "### Summary — dual payload"),
            "trit", NAME_EN,
        )
        self._check_table(
            _section_rows(text, "### Summary — dual payload", "### What the columns say"),
            "dual", NAME_EN,
        )


class ScenarioModel(unittest.TestCase):
    def test_weights_sum_to_100(self):
        weights = rows("scenario_weights.csv")
        self.assertEqual(len(weights), 5)
        for row in weights:
            total = sum(int(row[m]) for m in METRIC_ORDER)
            self.assertEqual(total, 100, row["scenario"])
            self.assertIn(row["payload"], ("trit", "dual", "both"))

    def test_scores_match_a_fresh_computation(self):
        scorecard = rows("scorecard_raw.csv")
        layout = {(r["encoding"], r["payload"]): r for r in rows("encoding_layout.csv")}
        weights = {r["scenario"]: r for r in rows("scenario_weights.csv")}
        stored = {
            (r["scenario"], r["payload"], r["encoding"]): r
            for r in rows("scenario_scores.csv")
        }
        checked = 0
        for scenario, weights_row in weights.items():
            scope = weights_row["payload"]
            for payload in ("trit", "dual"):
                if scope != "both" and scope != payload:
                    continue
                group = [r for r in scorecard if r["payload"] == payload]
                entries = []
                def value_of(row, metric, payload=payload):
                    if metric == "selective_bytes":
                        return float(layout[(row["encoding"], payload)]["selective_bytes_worst"])
                    return float(row[metric])

                for row in group:
                    sub = {}
                    for metric in LOWER:
                        value = value_of(row, metric)
                        best = min(value_of(r, metric) for r in group)
                        sub[metric] = best / value
                    for metric in HIGHER:
                        sub[metric] = value_of(row, metric)
                    weighted = sum(
                        int(weights_row[m]) / 100.0 * sub[m] for m in LOWER + HIGHER
                    ) * 100.0
                    entries.append((row["encoding"], sub, weighted))
                ranks = _competition_ranks([e[2] for e in entries], reverse=True)
                for (encoding, sub, weighted), rank in zip(entries, ranks):
                    got = stored[(scenario, payload, encoding)]
                    with self.subTest(scenario=scenario, payload=payload, encoding=encoding):
                        for metric in LOWER + HIGHER:
                            self.assertAlmostEqual(
                                float(got[f"score_{metric}"]), sub[metric], places=5
                            )
                        self.assertAlmostEqual(float(got["weighted_score"]), weighted, places=5)
                        self.assertEqual(int(got["rank"]), rank)
                    checked += 1
        self.assertEqual(checked, len(stored))
        self.assertEqual(checked, 60)

    def test_rendered_scenario_tables(self):
        winners = {
            (r["scenario"], r["payload"]): r
            for r in rows("scenario_scores.csv") if r["rank"] == "1"
        }
        runners = {}
        for row in rows("scenario_scores.csv"):
            key = (row["scenario"], row["payload"])
            if int(row["rank"]) > 1:
                runners.setdefault(key, row)
        sources = (
            ("README.md", NAME_EN, "#### Conditional weights: five scenarios"),
            ("README.zh-CN.md", NAME_ZH, "#### 条件权重：五组场景"),
            ("benchmarks/README.md", NAME_EN, "## `scenario_scores.csv` — generated"),
        )
        for readme, mapping, marker in sources:
            text = read(readme)
            end = "## `bandwidth_sweep.csv` — generated" if readme == "benchmarks/README.md" else None
            table_rows = [c for c in _section_rows(text, marker, end) if len(c) == 6]
            self.assertGreaterEqual(len(table_rows), 7)
            for cells in table_rows:
                key = (cells[0], cells[1])
                winner = winners[key]
                runner = runners[key]
                with self.subTest(readme=readme, scenario=cells[0], payload=cells[1]):
                    self.assertEqual(_name([cells[2]], mapping), winner["encoding"])
                    self.assertAlmostEqual(float(cells[3]), float(winner["weighted_score"]), delta=0.05)
                    self.assertEqual(_name([cells[4]], mapping), runner["encoding"])
                    self.assertAlmostEqual(float(cells[5]), float(runner["weighted_score"]), delta=0.05)

    def test_rendered_weight_tables(self):
        weights = {r["scenario"]: r for r in rows("scenario_weights.csv")}
        sources = (
            ("README.md", "#### Conditional weights: five scenarios"),
            ("README.zh-CN.md", "#### 条件权重：五组场景"),
            ("benchmarks/README.md", "## `scenario_weights.csv` — policy, not measurement"),
        )
        for readme, marker in sources:
            text = read(readme)
            tables = [c for c in _section_rows(text, marker) if len(c) == 11]
            self.assertEqual(len(tables), 5)
            for cells in tables:
                row = weights[cells[0]]
                with self.subTest(readme=readme, scenario=cells[0]):
                    self.assertEqual(cells[1], row["payload"])
                    for index, metric in enumerate(METRIC_ORDER, start=2):
                        self.assertEqual(int(cells[index]), int(row[metric]))


class BandwidthModel(unittest.TestCase):
    def test_sweep_matches_a_fresh_computation(self):
        scorecard = rows("scorecard_raw.csv")
        stored = {
            (r["payload"], r["encoding"], r["bandwidth_gbps"]): r
            for r in rows("bandwidth_sweep.csv")
        }
        checked = 0
        for payload in ("trit", "dual"):
            group = [r for r in scorecard if r["payload"] == payload]
            for bandwidth in (1, 3, 10, 30, 100, 300, 1000):
                entries = []
                for row in group:
                    bits = float(row["bits_per_element"])
                    bytes_per_element = bits / 8.0
                    compute = float(row["decode_ns_native"])
                    memory = bytes_per_element / bandwidth
                    entries.append(
                        (row["encoding"], bits, bytes_per_element, compute, memory,
                         max(compute, memory))
                    )
                ranks = _competition_ranks([e[5] for e in entries], reverse=False)
                for entry, rank in zip(entries, ranks):
                    encoding, bits, bytes_per_element, compute, memory, effective = entry
                    got = stored[(payload, encoding, str(bandwidth))]
                    with self.subTest(payload=payload, bandwidth=bandwidth, encoding=encoding):
                        self.assertAlmostEqual(float(got["bits_per_element"]), bits, delta=1e-6)
                        self.assertAlmostEqual(float(got["bytes_per_element"]), bytes_per_element, delta=1e-6)
                        self.assertAlmostEqual(float(got["decode_compute_ns"]), compute, delta=1e-9)
                        self.assertAlmostEqual(float(got["memory_ns"]), memory, delta=1e-6)
                        self.assertAlmostEqual(float(got["effective_ns"]), effective, delta=1e-6)
                        self.assertEqual(got["dominant"], "compute" if compute >= memory else "memory")
                        self.assertEqual(int(got["rank"]), rank)
                    checked += 1
        self.assertEqual(checked, len(stored))
        self.assertEqual(checked, 105)

    def test_rendered_bandwidth_tables(self):
        stored = {}
        for row in rows("bandwidth_sweep.csv"):
            stored.setdefault((row["payload"], row["bandwidth_gbps"]), []).append(row)
        sources = (
            ("README.md", NAME_EN, "#### Physical cost model"),
            ("README.zh-CN.md", NAME_ZH, "#### 物理成本模型"),
            ("benchmarks/README.md", NAME_EN, "## `bandwidth_sweep.csv` — generated"),
        )
        for readme, mapping, marker in sources:
            text = read(readme)
            end = "## `composite_scores.csv` — generated" if readme == "benchmarks/README.md" else None
            tables = [c for c in _section_rows(text, marker, end) if len(c) == 5]
            self.assertEqual(len(tables), 7)
            for cells in tables:
                bandwidth = cells[0]
                for payload, name_cell, ns_cell in (
                    ("trit", cells[1], cells[2]),
                    ("dual", cells[3], cells[4]),
                ):
                    top = [r for r in stored[(payload, bandwidth)] if r["rank"] == "1"]
                    expected = {_name([n], mapping) for n in name_cell.split(" / ")}
                    self.assertEqual(expected, {r["encoding"] for r in top})
                    self.assertAlmostEqual(float(ns_cell), float(top[0]["effective_ns"]), delta=0.0006)

    def test_crossover_shape(self):
        data = rows("bandwidth_sweep.csv")
        self.assertEqual(len(data), 105)
        self.assertEqual(len({r["bandwidth_gbps"] for r in data}), 7)
        at_one = [
            r for r in data
            if r["payload"] == "trit" and r["bandwidth_gbps"] == "1" and r["rank"] == "1"
        ]
        self.assertEqual(len(at_one), 3, "1 GB/s on trit is a three-way tie")
        at_hundred = [
            r for r in data
            if r["payload"] == "trit" and r["bandwidth_gbps"] == "100" and r["rank"] == "1"
        ]
        self.assertEqual({r["encoding"] for r in at_hundred}, {"fp16 dense", "int8 dense"})


class EncodingLayout(unittest.TestCase):
    def test_layout_matches_scorecard(self):
        raw = {(r["encoding"], r["payload"]): r for r in rows("scorecard_raw.csv")}
        layout = rows("encoding_layout.csv")
        self.assertEqual(len(layout), 15)
        self.assertEqual({(r["encoding"], r["payload"]) for r in layout}, set(raw))
        for row in layout:
            key = (row["encoding"], row["payload"])
            with self.subTest(key=key):
                self.assertEqual(int(row["payload_bytes"]), int(raw[key]["bytes_total"]))
                bit = int(row["bit_plane_bytes"])
                trit = int(row["trit_plane_bytes"])
                self.assertEqual(int(row["selective_bytes_bit"]), bit)
                self.assertEqual(int(row["selective_bytes_trit"]), trit)
                self.assertEqual(int(row["selective_bytes_worst"]), max(bit, trit))
                self.assertIn(int(row["frame_header_bytes"]), (0, 33))
                if row["layout"] in ("dual_plane", "dual_plane_omit_bit", "separate_arrays"):
                    self.assertEqual(bit + trit, int(row["payload_bytes"]))
                else:
                    self.assertEqual(bit, int(row["payload_bytes"]))
                    self.assertEqual(trit, int(row["payload_bytes"]))

    def test_dual_channel_sizes(self):
        layout = {(r["encoding"], r["payload"]): r for r in rows("encoding_layout.csv")}
        row = layout[("Dual6 dual-plane", "dual")]
        self.assertEqual(int(row["selective_bytes_bit"]), 8192)
        self.assertEqual(int(row["selective_bytes_trit"]), 13108)
        self.assertEqual(int(row["selective_bytes_worst"]), 13108)


class DecodeRatios(unittest.TestCase):
    def test_ratios_match_the_raw_csv(self):
        raw = {(r["encoding"], r["payload"]): r for r in rows("scorecard_raw.csv")}
        data = rows("decode_ratios.csv")
        self.assertEqual(len(data), 15)
        for row in data:
            key = (row["encoding"], row["payload"])
            reference = raw[(row["reference"], row["payload"])]
            with self.subTest(key=key):
                self.assertAlmostEqual(
                    float(row["ratio_raw_vs_reference"]),
                    float(reference["decode_ns_per_element"]) / float(row["decode_ns_per_element"]),
                    places=5,
                )
                self.assertAlmostEqual(
                    float(row["ratio_net_vs_reference"]),
                    float(reference["decode_ns_net"]) / float(row["decode_ns_net"]),
                    places=5,
                )
                self.assertAlmostEqual(
                    float(row["ratio_native_vs_reference"]),
                    float(reference["decode_ns_native"]) / float(row["decode_ns_native"]),
                    places=5,
                )
                clamped = (
                    1
                    if float(row["decode_ns_per_element"])
                    - float(raw[key]["py_loop_overhead_ns"])
                    < 0
                    else 0
                )
                self.assertEqual(int(row["decode_net_clamped"]), clamped)

    def test_int8_is_the_clamped_row(self):
        data = rows("decode_ratios.csv")
        int8 = next(r for r in data if r["payload"] == "trit" and r["encoding"] == "int8 dense")
        self.assertEqual(int(int8["decode_net_clamped"]), 1)
        self.assertAlmostEqual(float(int8["ratio_raw_vs_reference"]), 4.87, delta=0.01)
        self.assertAlmostEqual(float(int8["ratio_net_vs_reference"]), 591.75, delta=0.1)
        self.assertAlmostEqual(float(int8["ratio_native_vs_reference"]), 12.8, delta=0.1)


class WeightSensitivity(unittest.TestCase):
    def test_shares_sum_to_one(self):
        data = rows("weight_sensitivity.csv")
        self.assertEqual(len(data), 45)
        groups = {}
        for row in data:
            groups.setdefault((row["payload"], row["scheme"]), []).append(row)
        for key, group in groups.items():
            with self.subTest(key=key):
                self.assertAlmostEqual(sum(float(r["share"]) for r in group), 1.0, places=5)
                self.assertEqual(sum(int(r["wins"]) for r in group), int(group[0]["draws"]))

    def test_random_simplex_headline(self):
        data = rows("weight_sensitivity.csv")

        def share(payload, encoding):
            return float(
                next(
                    r["share"]
                    for r in data
                    if r["payload"] == payload
                    and r["scheme"] == "s1"
                    and r["encoding"] == encoding
                )
            )

        self.assertAlmostEqual(share("trit", "int8 dense"), 0.8598, delta=0.005)
        self.assertAlmostEqual(
            share("trit", "Dual6 dual-plane (trit-only frame)"), 0.1314, delta=0.01
        )
        self.assertAlmostEqual(share("dual", "int8 dense"), 0.8378, delta=0.005)
        self.assertAlmostEqual(share("dual", "Dual6 dual-plane"), 0.1596, delta=0.01)


class WeightSweeps(unittest.TestCase):
    def _score(self, layout, scorecard, payload, analysis, parameter, encoding):
        group = [r for r in scorecard if r["payload"] == payload]

        def value_of(row, metric):
            if metric == "selective_bytes":
                return float(layout[(row["encoding"], payload)]["selective_bytes_worst"])
            return float(row[metric])

        best = {m: min(value_of(r, m) for r in group) for m in LOWER}
        row = next(r for r in group if r["encoding"] == encoding)
        sub = {m: best[m] / value_of(row, m) for m in LOWER}
        sub.update({m: value_of(row, m) for m in HIGHER})
        if analysis == "structural":
            weights = {m: (100.0 - parameter) / len(LOWER) for m in LOWER}
            weights["integrity"] = parameter / 2.0
            weights["single_object"] = parameter / 2.0
        else:
            target = "bits_per_element" if analysis == "storage" else "selective_bytes"
            weights = {
                m: (100.0 - parameter) / (len(LOWER) + len(HIGHER) - 1)
                for m in LOWER + HIGHER
                if m != target
            }
            weights[target] = float(parameter)
        return sum(weights[m] / 100.0 * sub[m] for m in LOWER + HIGHER) * 100.0

    def test_sweep_shape_and_flip_points(self):
        data = rows("weight_sweeps.csv")
        self.assertEqual(len(data), 756)
        layout = {(r["encoding"], r["payload"]): r for r in rows("encoding_layout.csv")}
        scorecard = rows("scorecard_raw.csv")
        for analysis, payload, parameter, encoding in (
            ("structural", "trit", 0, "int8 dense"),
            ("structural", "trit", 45, "Dual6 dual-plane (trit-only frame)"),
            ("storage", "trit", 30, "Dual6 dual-plane (trit-only frame)"),
            ("selective", "dual", 25, "Dual6 dual-plane"),
            ("selective", "dual", 100, "Dual6 dual-plane"),
        ):
            stored = next(
                float(r["score"])
                for r in data
                if r["analysis"] == analysis
                and r["payload"] == payload
                and int(r["parameter"]) == parameter
                and r["encoding"] == encoding
            )
            expected = self._score(layout, scorecard, payload, analysis, parameter, encoding)
            with self.subTest(analysis=analysis, payload=payload, parameter=parameter):
                self.assertAlmostEqual(stored, expected, places=5)

        def score(analysis, payload, parameter, encoding):
            return next(
                float(r["score"])
                for r in data
                if r["analysis"] == analysis
                and r["payload"] == payload
                and int(r["parameter"]) == parameter
                and r["encoding"] == encoding
            )

        dual6 = "Dual6 dual-plane (trit-only frame)"
        self.assertGreater(
            score("structural", "trit", 45, dual6),
            score("structural", "trit", 45, "int8 dense"),
        )
        self.assertLess(
            score("structural", "trit", 40, dual6),
            score("structural", "trit", 40, "int8 dense"),
        )
        self.assertGreater(
            score("selective", "dual", 25, "Dual6 dual-plane"),
            score("selective", "dual", 25, "int8 dense"),
        )
        self.assertLess(
            score("selective", "dual", 20, "Dual6 dual-plane"),
            score("selective", "dual", 20, "int8 dense"),
        )



class ModelRoundtrip(unittest.TestCase):
    def test_csv_shape_and_exactness(self):
        data = rows("model_roundtrip.csv")
        self.assertGreaterEqual(len(data), 2)
        self.assertEqual({r["scope"] for r in data}, {"all_2d", "linears"})
        for row in data:
            with self.subTest(scope=row["scope"]):
                self.assertEqual(int(row["weights_exact"]), 1)
                self.assertEqual(int(row["logits_exact"]), 1)
                self.assertEqual(float(row["max_logit_diff"]), 0.0)
                self.assertEqual(float(row["top1_agreement"]), 1.0)
                self.assertEqual(
                    int(row["dual6_header_bytes"]), int(row["frames"]) * 33
                )
                self.assertEqual(
                    int(row["dual6_encoded_total_bytes"]),
                    int(row["dual6_payload_bytes"])
                    + int(row["dual6_header_bytes"])
                    + int(row["dual6_scale_bytes"]),
                )

    def test_check_csv_mode(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "model_roundtrip.py"), "--check-csv"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_headline_numbers(self):
        data = {r["scope"]: r for r in rows("model_roundtrip.csv")}
        linears = data["linears"]
        self.assertEqual(int(linears["encoded_elements"]), 84934656)
        self.assertEqual(int(linears["frames"]), 1296)
        self.assertEqual(int(linears["dual6_payload_bytes"]), 16987968)
        self.assertEqual(int(linears["dual6_header_bytes"]), 42768)
        self.assertEqual(int(linears["dual6_encoded_total_bytes"]), 17030928)
        self.assertEqual(int(linears["dual6_model_total_bytes"]), 96041232)
        self.assertAlmostEqual(float(linears["dual6_bpw_encoded"]), 1.604144, places=5)
        self.assertAlmostEqual(float(linears["dual6_bpw_overall"]), 6.174309, places=5)
        self.assertAlmostEqual(float(linears["int8_bpw_overall"]), 10.5397, places=3)

        all_2d = data["all_2d"]
        self.assertEqual(int(all_2d["encoded_elements"]), 124318464)
        self.assertEqual(int(all_2d["frames"]), 1897)
        self.assertEqual(int(all_2d["dual6_payload_bytes"]), 24865210)
        self.assertEqual(int(all_2d["dual6_header_bytes"]), 62601)
        self.assertEqual(int(all_2d["dual6_encoded_total_bytes"]), 24928011)
        self.assertEqual(int(all_2d["dual6_model_total_bytes"]), 25170699)


class CompositeScores(unittest.TestCase):
    def test_scores_match_a_fresh_computation(self):
        scorecard = rows("scorecard_raw.csv")
        layout = {(r["encoding"], r["payload"]): r for r in rows("encoding_layout.csv")}
        taxonomy = {(r["encoding"], r["payload"]): r for r in rows("encoding_taxonomy.csv")}
        stored = {
            (r["payload"], r["encoding"]): r for r in rows("composite_scores.csv")
        }
        self.assertEqual(len(stored), 15)
        checked = 0
        for payload in ("trit", "dual"):
            group = [r for r in scorecard if r["payload"] == payload]

            def value_of(row, metric, payload=payload):
                if metric == "selective_bytes":
                    return float(layout[(row["encoding"], payload)]["selective_bytes_worst"])
                return float(row[metric])

            best = {m: min(value_of(r, m) for r in group) for m in LOWER}
            entries = []
            for row in group:
                sub = {m: best[m] / value_of(row, m) for m in LOWER}
                sub.update({m: value_of(row, m) for m in HIGHER})
                tax = taxonomy[(row["encoding"], payload)]
                sub["information_utilization"] = float(
                    tax["info_bits_per_element"]
                ) / float(tax["storage_bits_per_element"])
                composite = (
                    sum(sub[m] for m in LOWER + HIGHER + ("information_utilization",))
                    / (len(LOWER) + len(HIGHER) + 1)
                    * 100
                )
                entries.append((row["encoding"], sub, composite))
            ranks = _competition_ranks([e[2] for e in entries], reverse=True)
            for (encoding, sub, composite), rank in zip(entries, ranks):
                got = stored[(payload, encoding)]
                with self.subTest(payload=payload, encoding=encoding):
                    for metric in LOWER + HIGHER:
                        self.assertAlmostEqual(
                            float(got[f"score_{metric}"]), sub[metric], places=5
                        )
                    self.assertAlmostEqual(
                        float(got["score_information_utilization"]),
                        sub["information_utilization"],
                        places=5,
                    )
                    self.assertAlmostEqual(float(got["composite_score"]), composite, places=5)
                    self.assertEqual(int(got["rank"]), rank)
                checked += 1
        self.assertEqual(checked, 15)

    def test_equal_weight_ranking(self):
        data = {(r["payload"], r["encoding"]): r for r in rows("composite_scores.csv")}
        self.assertEqual(data[("trit", "int8 dense")]["rank"], "1")
        self.assertEqual(data[("dual", "int8 dense")]["rank"], "1")
        self.assertEqual(data[("trit", "Dual6 dual-plane (trit-only frame)")]["rank"], "2")
        self.assertEqual(data[("dual", "Dual6 dual-plane")]["rank"], "2")
        self.assertAlmostEqual(
            float(data[("trit", "int8 dense")]["composite_score"]), 66.0, delta=0.1
        )
        self.assertAlmostEqual(
            float(data[("dual", "int8 dense")]["composite_score"]), 64.2, delta=0.1
        )

    def test_rendered_tables(self):
        data = {(r["payload"], r["encoding"]): r for r in rows("composite_scores.csv")}
        for readme, mapping, marker, end in (
            ("README.md", NAME_EN, "#### Comprehensive score: T and I (equal weights)",
             "#### Conditional weights"),
            ("README.zh-CN.md", NAME_ZH, "#### 综合评分：T 与 I（等权）",
             "#### 条件权重"),
        ):
            text = read(readme)
            table_rows = [c for c in _section_rows(text, marker, end) if len(c) == 13]
            self.assertEqual(len(table_rows), 15)
            for index, cells in enumerate(table_rows):
                encoding = _name([cells[1]], mapping)
                # Table order: first 9 rows trit, next 6 dual.
                payload = "trit" if index < 9 else "dual"
                got = data[(payload, encoding)]
                with self.subTest(readme=readme, encoding=encoding, payload=payload):
                    self.assertEqual(int(cells[0]), int(got["rank"]))
                    self.assertAlmostEqual(
                        float(cells[11].replace("%", "")),
                        float(got["utilization_pct"]),
                        delta=0.1,
                    )
                    self.assertAlmostEqual(float(cells[12]), float(got["composite_score"]), delta=0.05)




class XSDecode(unittest.TestCase):
    def test_measured_cases(self):
        data = {(r["backend"], r["case"]): r for r in rows("xs_decode.csv")}
        cases = {
            "digit_decode", "I_bit_channel", "I_trit_channel", "I_dual_plane_full",
            "X_demux", "X_binary_view", "X_ternary_view", "S_trit_plus_bit",
        }
        self.assertEqual({case for _, case in data}, cases)
        self.assertEqual({backend for backend, _ in data}, {"ref", "native"})
        for key, row in data.items():
            with self.subTest(key=key):
                self.assertGreater(float(row["ns_per_element"]), 0)
        self.assertAlmostEqual(float(data[("ref", "X_demux")]["ns_per_element"]), 137.4, delta=10.0)
        self.assertAlmostEqual(float(data[("native", "X_demux")]["ns_per_element"]), 23.8, delta=3.0)
        self.assertAlmostEqual(float(data[("native", "I_bit_channel")]["ns_per_element"]), 5.1, delta=2.0)
        self.assertAlmostEqual(float(data[("native", "I_trit_channel")]["ns_per_element"]), 5.9, delta=2.0)
        self.assertAlmostEqual(float(data[("native", "I_dual_plane_full")]["ns_per_element"]), 19.0, delta=3.0)
        self.assertAlmostEqual(float(data[("native", "S_trit_plus_bit")]["ns_per_element"]), 30.8, delta=5.0)
        self.assertAlmostEqual(float(data[("ref", "X_binary_view")]["ns_per_element"]), 118.0, delta=10.0)
        self.assertAlmostEqual(float(data[("ref", "X_ternary_view")]["ns_per_element"]), 110.4, delta=10.0)
        self.assertLess(
            float(data[("native", "X_demux")]["ns_per_element"]),
            float(data[("ref", "X_demux")]["ns_per_element"]),
        )


class XSScores(unittest.TestCase):
    def test_mixed_rows(self):
        data = {r["data_model"]: r for r in rows("xs_scores.csv")}
        self.assertEqual(set(data), {"X", "S"})
        for model, row in data.items():
            with self.subTest(model=model):
                self.assertEqual(row["evidence"], "mixed_native_decode")
                self.assertEqual(row["decode_backend"], "native_batch")
                self.assertIn("xs_decode.csv", row["proxy_source"])
                self.assertIn("native batch", row["proxy_source"])
                self.assertIn("Dual6 dual-plane", row["proxy_source"])
                utilization = float(row["info_bits_per_element"]) / float(
                    row["storage_bits_per_element"]
                )
                self.assertAlmostEqual(
                    float(row["score_information_utilization"]), utilization, places=6
                )
        self.assertGreater(
            float(data["S"]["composite_score"]), float(data["X"]["composite_score"])
        )
        self.assertAlmostEqual(float(data["S"]["composite_score"]), 57.5, delta=0.2)
        self.assertAlmostEqual(float(data["X"]["composite_score"]), 56.3, delta=0.2)

    def test_rendered_xs_table(self):
        data = {r["data_model"]: r for r in rows("xs_scores.csv")}
        for readme in ("README.md", "README.zh-CN.md"):
            text = read(readme)
            if readme == "README.md":
                marker, end = "#### Comprehensive score: T and I (equal weights)", "#### Conditional weights"
            else:
                marker, end = "#### 综合评分：T 与 I（等权）", "#### 条件权重"
            table_rows = [c for c in _section_rows(text, marker, end) if len(c) == 6]
            self.assertEqual(len(table_rows), 2)
            for cells in table_rows:
                model = cells[2]
                got = data[model]
                with self.subTest(readme=readme, model=model):
                    self.assertAlmostEqual(float(cells[4]), float(got["composite_score"]), delta=0.05)


class DataModels(unittest.TestCase):
    def test_four_models_and_math(self):
        data = {r["data_model"]: r for r in rows("data_models.csv")}
        self.assertEqual(set(data), {"T", "I", "X", "S"})
        for model, row in data.items():
            with self.subTest(model=model):
                info = float(row["info_bits_per_element"])
                storage = float(row["dual6_storage_bits_per_element"])
                self.assertAlmostEqual(
                    float(row["utilization_pct"]), info / storage * 100, places=4
                )
        self.assertAlmostEqual(float(data["T"]["utilization_pct"]), 99.06, delta=0.01)
        self.assertAlmostEqual(float(data["I"]["utilization_pct"]), 99.42, delta=0.01)
        self.assertAlmostEqual(float(data["X"]["utilization_pct"]), 38.46, delta=0.01)
        self.assertAlmostEqual(float(data["S"]["utilization_pct"]), 60.96, delta=0.01)
        self.assertEqual(data["X"]["interconvertible"], "yes")
        self.assertEqual(data["S"]["interconvertible"], "no")

    def test_readme_data_model_tables(self):
        data = {r["data_model"]: r for r in rows("data_models.csv")}
        for readme, marker, end in (
            ("README.md", "#### Data models: T, I, X, S", "#### Nine scored metrics"),
            ("README.zh-CN.md", "#### 数据模型：T、I、X、S", "#### 九项计分指标"),
        ):
            text = read(readme)
            table_rows = [c for c in _section_rows(text, marker, end) if len(c) == 7]
            self.assertEqual(len(table_rows), 4)
            for model, cells in zip(("T", "I", "X", "S"), table_rows):
                with self.subTest(readme=readme, model=model):
                    self.assertAlmostEqual(
                        float(cells[2]), float(data[model]["info_bits_per_element"]), delta=0.001
                    )
                    self.assertAlmostEqual(
                        float(cells[3].split()[0]),
                        float(data[model]["dual6_storage_bits_per_element"]),
                        delta=0.001,
                    )
                    util = float(cells[4].replace("*", "").replace("%", ""))
                    self.assertAlmostEqual(
                        util, float(data[model]["utilization_pct"]), delta=0.1
                    )


class EncodingTaxonomy(unittest.TestCase):
    def test_taxonomy_matches_scorecard(self):
        raw = {(r["encoding"], r["payload"]): r for r in rows("scorecard_raw.csv")}
        tax = rows("encoding_taxonomy.csv")
        self.assertEqual(len(tax), 15)
        self.assertEqual({(r["encoding"], r["payload"]) for r in tax}, set(raw))
        models = {r["data_model"] for r in tax}
        self.assertEqual(models, {"T", "I"})
        self.assertEqual(sum(r["data_model"] == "T" for r in tax), 9)
        self.assertEqual(sum(r["data_model"] == "I" for r in tax), 6)
        for row in tax:
            key = (row["encoding"], row["payload"])
            with self.subTest(key=key):
                self.assertEqual(row["data_model"], "T" if row["payload"] == "trit" else "I")
                self.assertAlmostEqual(
                    float(row["storage_bits_per_element"]),
                    float(raw[key]["bits_per_element"]),
                    places=5,
                )
                info = float(row["info_bits_per_element"])
                storage = float(row["storage_bits_per_element"])
                self.assertAlmostEqual(float(row["utilization_pct"]), info / storage * 100, places=4)


class InformationBudget(unittest.TestCase):
    def test_budget_matches_data_models(self):
        models = {r["data_model"]: r for r in rows("data_models.csv")}
        budget = {r["data_model"]: r for r in rows("information_budget.csv")}
        self.assertEqual(set(budget), {"T", "I", "X", "S"})
        for model, row in budget.items():
            with self.subTest(model=model):
                source = models[model]
                self.assertAlmostEqual(
                    float(row["info_bits_per_element"]),
                    float(source["info_bits_per_element"]),
                    places=6,
                )
                self.assertAlmostEqual(
                    float(row["dual6_storage_bits_per_element"]),
                    float(source["dual6_storage_bits_per_element"]),
                    places=6,
                )
                self.assertAlmostEqual(
                    float(row["utilization_pct"]),
                    float(row["info_bits_per_element"])
                    / float(row["dual6_storage_bits_per_element"])
                    * 100,
                    places=4,
                )


class DerivedFilesAreFresh(unittest.TestCase):
    def test_make_scores_check(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "make_scores.py"), "--check"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


class RatioClaims(unittest.TestCase):
    def test_ratio_claims(self):
        data = {r["encoding"]: r for r in rows("scorecard_raw.csv") if r["payload"] == "trit"}
        int8 = data["int8 dense"]
        trit_only = data["Dual6 dual-plane (trit-only frame)"]
        ratio = float(trit_only["decode_ns_net"]) / float(int8["decode_ns_net"])
        self.assertGreater(ratio, 100, "the README quotes 592x")
        self.assertAlmostEqual(float(int8["bits_per_element"]) / float(trit_only["bits_per_element"]), 5.0, delta=0.01)
        text = read("benchmarks/README.md")
        self.assertIn("592×", text)
        self.assertIn("5× more", text)
        dual = data["Dual6 dual-plane"]
        trit = data["Dual6 dual-plane (trit-only frame)"]
        self.assertAlmostEqual(
            float(dual["bits_per_element"]) / float(trit["bits_per_element"]), 1.62, delta=0.01
        )
        readme = read("README.md")
        for claim in ("1.62×", "4.87×", "8192 B", "13108 B", "131072 B"):
            self.assertIn(claim, readme)
        zh = read("README.zh-CN.md")
        for claim in ("1.62×", "4.87", "8192 B", "13108 B", "131072 B"):
            self.assertIn(claim, zh)


class MaskStructure(unittest.TestCase):
    def test_density_is_identical_across_structures(self):
        data = rows("mask_structure.csv")
        densities = {float(r["density"]) for r in data}
        self.assertEqual(len(densities), 1)
        self.assertAlmostEqual(densities.pop(), 0.05, places=3)

    def test_clustered_masks_save_and_periodic_scatter_does_not(self):
        data = {r["structure"]: r for r in rows("mask_structure.csv")}
        for name in ("columns (8-wide)", "columns (64-wide)", "runs (64)"):
            with self.subTest(structure=name):
                self.assertLess(float(data[name]["delta_mean_pct"]), -20.0)
        self.assertGreater(float(data["scatter (periodic)"]["delta_mean_pct"]), 0.0)

    def test_empty_block_share_follows_the_saving(self):
        data = sorted(rows("mask_structure.csv"), key=lambda r: float(r["empty_blocks_pct"]))
        deltas = [float(r["delta_mean_pct"]) for r in data]
        for a, b in zip(deltas, deltas[1:]):
            self.assertLessEqual(b, a + 1e-9)


class SparsePlane(unittest.TestCase):
    def test_crossover_is_where_the_readme_says(self):
        # 5% density must save, 20% must not
        data = rows("sparse_plane.csv")
        block24 = {round(float(r["density"]), 3): r for r in data if r["block_symbols"] == "24"}
        self.assertLess(float(block24[0.05]["delta_pct"]), 0)
        self.assertGreater(float(block24[0.2]["delta_pct"]), 0)


class FaultSize(unittest.TestCase):
    def test_small_payloads_do_not_tear_and_big_ones_do(self):
        data = {int(r["payload_bytes"]): r for r in rows("fault_size.csv")}
        self.assertEqual(int(data[4096]["silent"]), 0)
        self.assertEqual(int(data[65536]["silent"]), 0)
        self.assertGreater(int(data[8 * 1024 * 1024]["silent"]), 0)


class FaultMatrix(unittest.TestCase):
    def test_checksum_and_rename_remove_silent_corruption(self):
        race = {
            (r["format"], r["protocol"], r["loader"]): int(r["silent"])
            for r in rows("fault_matrix.csv")
            if r["fault"] == "race"
        }
        self.assertEqual(race[("dual6-P2-crc", "in_place_rplus", "naive")], 0)
        for key, value in race.items():
            if key[1] == "rename" or key[2] == "hash":
                with self.subTest(cell=key):
                    self.assertEqual(value, 0)


class ReadmeClaims(unittest.TestCase):
    """Numbers in the narrative sections must trace back to a CSV."""

    def test_premium_and_parity_claims(self):
        data = {(r["encoding"], r["payload"]): r for r in rows("scorecard_raw.csv")}
        trit_only = data[("Dual6 dual-plane (trit-only frame)", "trit")]
        tq1 = data[("TQ1_0 (5 trit/byte)", "trit")]
        dual = data[("Dual6 dual-plane", "dual")]

        premium = float(dual["bits_per_element"]) / float(tq1["bits_per_element"]) - 1
        self.assertAlmostEqual(premium, 0.625, delta=0.01)      # README: 62.5%
        self.assertAlmostEqual(
            float(trit_only["bits_per_element"]),
            float(tq1["bits_per_element"]), delta=0.001,
        )

        text = read("README.md")
        for claim in ("62.5%", "1.60 bpw", "59.2 ns", "2.6 bpw"):
            with self.subTest(claim=claim):
                self.assertIn(claim, text)

    def test_fault_threshold_claim(self):
        data = {int(r["payload_bytes"]): r for r in rows("fault_size.csv")}
        small = [data[s] for s in (4096, 65536)]
        for r in small:
            with self.subTest(size=r["payload_bytes"]):
                self.assertEqual(int(r["silent"]), 0)
        self.assertGreater(int(data[512 * 1024]["silent"]), 0)
        self.assertIn("64 KiB and 512 KiB", read("README.md"))


class ReadmeSnippets(unittest.TestCase):
    """Every ```python block in the README must run as printed."""

    def test_python_blocks_execute(self):
        import subprocess
        import sys
        import tempfile
        import textwrap

        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "python"))
        for readme in ("README.md", "README.zh-CN.md"):
            if not os.path.exists(os.path.join(ROOT, readme)):
                continue
            text = read(readme)
            blocks = re.findall("```python" + chr(10) + "(.*?)```", text, re.S)
            self.assertGreaterEqual(len(blocks), 2, readme)
            with tempfile.TemporaryDirectory() as tmp:
                for i, block in enumerate(blocks, 1):
                    with self.subTest(readme=readme, block=i):
                        done = subprocess.run(
                            [sys.executable, "-c", textwrap.dedent(block)],
                            capture_output=True, text=True, env=env, cwd=tmp,
                            check=False,
                        )
                        self.assertEqual(done.returncode, 0, done.stderr)


class ReadmeQuotes(unittest.TestCase):
    def test_headline_numbers_appear_in_the_readme(self):
        text = read("README.md")
        self.assertIn("1.60 bpw", text)
        self.assertIn("59.2 ns", text)
        self.assertIn("−25%", text)

    def test_chinese_readme_matches(self):
        if not os.path.exists(os.path.join(ROOT, "README.zh-CN.md")):
            self.skipTest("no Chinese README")
        zh = read("README.zh-CN.md")
        for claim in ("1.60 bpw", "59.2 ns", "62.5%", "−25%", "64 KiB", "326"):
            with self.subTest(claim=claim):
                self.assertIn(claim, zh)
        self.assertIn("README.md", zh)          # language switcher back

    def test_naming_is_documented(self):
        for readme in ("README.md", "README.zh-CN.md"):
            text = read(readme)
            with self.subTest(readme=readme):
                self.assertIn(".p6", text)
                self.assertIn("二生三", text)
                self.assertIn("perfect number" if readme == "README.md" else "完全数", text)
                # it is the *model* file extension, not just any frame
                self.assertIn("model" if readme == "README.md" else "模型", text)
                self.assertIn("llama-3-8b.p6", text)

    def test_fit_and_outlook_are_documented(self):
        """The README must say where it does *not* fit, not only where it does."""
        en = read("README.md")
        zh = read("README.zh-CN.md")
        for phrase in ("Where it actually fits", "Where it does not fit", "Outlook"):
            with self.subTest(section=phrase):
                self.assertIn(phrase, en)
        for phrase in ("实际可能适用的场景", "明确不适用的地方", "展望"):
            with self.subTest(section=phrase):
                self.assertIn(phrase, zh)
        # the non-fit list has to mention the competing formats by name
        for fmt in ("TQ1_0", "int8"):
            with self.subTest(format=fmt):
                self.assertIn(fmt, en)
        # the "moat" claim has to be corrected: the protocol protects, not the container
        self.assertIn("not by how the bytes are packed", en)
        self.assertIn("not a property of the container", en.lower())
        # the hypothetical nature of the per-element side channel must be stated
        self.assertIn("currently hypothetical", en)

    def test_use_cases_doc_exists_and_matches_the_data(self):
        path = os.path.join(ROOT, "docs", "13-use-cases.md")
        self.assertTrue(os.path.exists(path))
        text = read("docs/13-use-cases.md")
        data = {int(r["payload_bytes"]): r for r in rows("fault_size.csv")}
        for size, pct in ((512 * 1024, "1.5"), (2 * 1024 * 1024, "17.0"), (8 * 1024 * 1024, "26.5")):
            with self.subTest(size=size):
                self.assertIn(pct, text)
                self.assertAlmostEqual(float(data[size]["silent_pct"]), float(pct), places=1)

    def test_license_is_declared(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "LICENSE")))
        self.assertIn("MIT", read("LICENSE"))
        self.assertIn("MIT", read("README.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
