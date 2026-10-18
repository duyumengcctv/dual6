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
            ["fault-size.png", "mask-structure.png", "scorecard.png", "sparse-plane.png"],
        )

    def test_every_chart_is_referenced_by_a_readme(self):
        for readme in ("README.md", "README.zh-CN.md"):
            text = read(readme)
            for name in ("scorecard.png", "sparse-plane.png", "mask-structure.png",
                         "fault-size.png"):
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
        import re
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
        for claim in ("1.60 bpw", "59.2 ns", "62.5%", "−25%", "64 KiB", "284"):
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
