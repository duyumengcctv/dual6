"""Regenerate the charts in ``benchmarks/charts`` from the CSVs.

Pure rendering: every number comes from ``benchmarks/*.csv``, nothing is typed
in by hand. Requires matplotlib (not a runtime dependency of the package):

    pip install matplotlib
    python tools/make_charts.py
"""

from __future__ import annotations

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "benchmarks")
OUT = os.path.join(BENCH, "charts")

D6 = "#F76707"
TQ = "#4C6EF5"
GREY = "#ADB5BD"
BAD = "#E03131"
GOOD = "#2F9E44"
PURPLE = "#7048E8"

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": ":",
        "axes.unicode_minus": False,
        "figure.autolayout": True,
    }
)


def rows(name):
    with open(os.path.join(BENCH, name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.relpath(path, ROOT))


def chart_scorecard():
    """Storage against decode cost for every encoding in the battery."""
    data = [r for r in rows("scorecard_raw.csv") if r["payload"] == "trit"]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for r in data:
        name = r["encoding"]
        x = float(r["bits_per_element"])
        y = float(r["decode_ns_net"])
        if "trit-only" in name:
            color, marker, size = D6, "*", 220
        elif name == "Dual6 dual-plane":
            color, marker, size = PURPLE, "s", 70
        elif name.startswith("TQ1_0"):
            color, marker, size = TQ, "o", 80
        else:
            color, marker, size = GREY, "o", 55
        ax.scatter(x, y, s=size, color=color, marker=marker, zorder=3,
                   edgecolors="white", linewidths=0.6)
        ax.annotate(name.replace(" (5 trit/byte)", "").replace(" (trit-only frame)", " †"),
                    (x, y), textcoords="offset points", xytext=(6, 5), fontsize=6.5,
                    color=color if color != GREY else "#495057")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("storage (bits per element, log)")
    ax.set_ylabel("decode (ns per element, log)")
    ax.set_title("Nine encodings: storage and decode cost")
    ax.text(0.02, 0.03, "† trit-only frame: same bytes as TQ1_0, plus a CRC",
            transform=ax.transAxes, fontsize=6.5, color="#6c757d")
    save(fig, "scorecard.png")


def chart_sparse_plane():
    data = rows("sparse_plane.csv")
    blocks = []
    for r in data:
        if r["block_symbols"] not in blocks:
            blocks.append(r["block_symbols"])
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    for i, block in enumerate(blocks):
        pts = sorted((float(r["density"]) * 100, float(r["delta_pct"]))
                     for r in data if r["block_symbols"] == block)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", ms=4,
                color=[D6, TQ, PURPLE][i % 3], label=f"block = {block} symbols")
    ax.axhline(0, color="#333", lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("mask density (%), log")
    ax.set_ylabel("size change vs fixed bit plane (%)")
    ax.set_title("Compacted bit plane: pays below ~10% density")
    ax.legend(frameon=False, fontsize=7.5)
    save(fig, "sparse-plane.png")


def chart_mask_structure():
    data = rows("mask_structure.csv")
    labels = [r["structure"] for r in data]
    mean = [float(r["delta_mean_pct"]) for r in data]
    lo = [float(r["delta_mean_pct"]) - float(r["delta_min_pct"]) for r in data]
    hi = [float(r["delta_max_pct"]) - float(r["delta_mean_pct"]) for r in data]
    empty = [float(r["empty_blocks_pct"]) for r in data]

    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    y = list(range(len(labels)))
    ax.barh(y, mean, color=[GOOD if m < 0 else BAD for m in mean], height=0.6)
    ax.errorbar(mean, y, xerr=[lo, hi], fmt="none", ecolor="#333", capsize=3, lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color="#333", lw=1)
    for yi, m, e in zip(y, mean, empty):
        ax.text(m + (1.2 if m >= 0 else -1.2), yi, f"{m:+.1f}%  ({e:.0f}% empty)",
                va="center", ha="left" if m >= 0 else "right", fontsize=6.8)
    ax.set_xlabel("size change vs fixed bit plane (%) — 5 replicates, exactly 5% density")
    ax.set_title("Compacted bit plane follows *clustering*, not density")
    save(fig, "mask-structure.png")


def chart_fault_size():
    data = rows("fault_size.csv")
    sizes = [int(r["payload_bytes"]) / 1024 for r in data]
    pct = [float(r["silent_pct"]) for r in data]
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    ax.plot(sizes, pct, "o-", color=BAD, lw=1.8, ms=6)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("payload size (KiB, log)")
    ax.set_ylabel("silent-corrupt reads (%)")
    ax.set_title("Small overwrites are atomic in practice; large ones are not")
    for x, y in zip(sizes, pct):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=7.5)
    ax.set_ylim(-1.5, max(pct) * 1.3)
    ax.axhline(0, color="#333", lw=0.8)
    save(fig, "fault-size.png")


def main():
    chart_scorecard()
    chart_sparse_plane()
    chart_mask_structure()
    chart_fault_size()


if __name__ == "__main__":
    main()
