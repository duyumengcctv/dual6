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
            "scenario_scores.csv",
            "bandwidth_sweep.csv",
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
                "fault-size.png",
                "mask-structure.png",
                "scenario-scores.png",
                "scorecard.png",
                "sparse-plane.png",
            ],
        )

    def test_every_chart_is_referenced_by_a_readme(self):
        for readme in ("README.md", "README.zh-CN.md"):
            text = read(readme)
            for name in ("scorecard.png", "sparse-plane.png", "mask-structure.png",
                         "fault-size.png", "scenario-scores.png", "bandwidth-crossover.png"):
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
    "Dual6 dual-plane (trit-only)": "Dual6 dual-plane (trit-only frame)",
    "Dual6 interleaved (13 bit)": "Dual6 interleaved (13 bit/5 sym)",
}
NAME_ZH = {
    "fp16 稠密": "fp16 dense",
    "int8 稠密": "int8 dense",
    "6 态 3-bit 槽": "6-state 3-bit slot",
    "Dual6 双平面": "Dual6 dual-plane",
    "Dual6 双平面（trit-only）": "Dual6 dual-plane (trit-only frame)",
    "Dual6 交错（13 bit）": "Dual6 interleaved (13 bit/5 sym)",
    "两份独立数组": "two separate arrays",
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
    "Bandwidth (GB/s)", "带宽 (GB/s)",
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
        expected = 9 if payload == "trit" else 6
        self.assertEqual(len(table_rows), expected)
        for cells in table_rows:
            name = _name(cells, mapping)
            row = data[(name, payload)]
            with self.subTest(encoding=name, payload=payload):
                self.assertAlmostEqual(float(cells[1]), float(row["bits_per_element"]), places=2)
                self.assertAlmostEqual(float(cells[2]), float(row["encode_ns_per_element"]), delta=0.05)
                self.assertAlmostEqual(float(cells[3]), float(row["decode_ns_net"]), delta=0.05)
                native = cells[4].replace("†", "")
                self.assertAlmostEqual(float(native), float(row["decode_ns_native"]), delta=0.0006)
                self.assertEqual("†" in cells[4], row["compute_source"] == "memcpy_floor")
                self.assertAlmostEqual(float(cells[5]), float(row["random_ns_net"]), delta=0.05)
                self.assertAlmostEqual(float(cells[6]), float(row["sparse_ns_net"]), delta=0.05)
                self.assertEqual(int(cells[7]), int(row["selective_bytes"]))
                self.assertEqual(cells[8] == "✓", row["integrity"] == "1")
                self.assertEqual(cells[9] == "✓", row["single_object"] == "1")

    def test_readme_english_tables(self):
        text = read("README.md")
        self._check_table(
            _section_rows(text, "#### Pure-trit payload", "#### Dual payload"),
            "trit", NAME_EN,
        )
        self._check_table(
            _section_rows(text, "#### Dual payload", "#### Five weight sets"),
            "dual", NAME_EN,
        )

    def test_readme_chinese_tables(self):
        text = read("README.zh-CN.md")
        self._check_table(
            _section_rows(text, "#### 纯三值载荷", "#### 双载荷"),
            "trit", NAME_ZH,
        )
        self._check_table(
            _section_rows(text, "#### 双载荷", "#### 五组权重"),
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
                for row in group:
                    sub = {}
                    for metric in LOWER:
                        value = float(row[metric])
                        best = min(float(r[metric]) for r in group)
                        sub[metric] = best / value
                    for metric in HIGHER:
                        sub[metric] = float(row[metric])
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
            ("README.md", NAME_EN, "#### Five weight sets"),
            ("README.zh-CN.md", NAME_ZH, "#### 五组权重"),
            ("benchmarks/README.md", NAME_EN, "## `scenario_scores.csv` — generated"),
        )
        for readme, mapping, marker in sources:
            text = read(readme)
            table_rows = [c for c in _section_rows(text, marker) if len(c) == 6]
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
            ("README.md", "#### Five weight sets"),
            ("README.zh-CN.md", "#### 五组权重"),
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
            tables = [c for c in _section_rows(text, marker) if len(c) == 5]
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
        for claim in ("1.62×", "8192 B", "131072 B"):
            self.assertIn(claim, readme)
        zh = read("README.zh-CN.md")
        for claim in ("1.62×", "8192 B", "131072 B"):
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
        for claim in ("1.60 bpw", "59.2 ns", "62.5%", "−25%", "64 KiB", "306"):
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
