"""Regenerate the charts in ``benchmarks/charts`` from the CSVs.

Pure rendering: every number comes from ``benchmarks/*.csv``, nothing is typed
in by hand. Requires matplotlib (not a runtime dependency of the package):

    pip install matplotlib
    python tools/make_charts.py
"""

from __future__ import annotations

import csv
import math
import os
import warnings

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
    with warnings.catch_warnings():
        # The colorbar + suptitle combination trips matplotlib's tight_layout
        # compatibility warning; bbox_inches="tight" still produces the right
        # crop, so keep the output clean without changing the layout engine.
        warnings.filterwarnings(
            "ignore",
            message="This figure includes Axes that are not compatible with tight_layout",
        )
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



ENCODING_COLORS = {
    "fp16 dense": "#868E96",
    "int8 dense": "#495057",
    "TQ1_0 (5 trit/byte)": TQ,
    "TQ2_0 (2 bit/trit)": "#748FFC",
    "6-state 3-bit slot": "#B197FC",
    "Dual6 dual-plane": PURPLE,
    "Dual6 dual-plane (trit-only frame)": D6,
    "Dual6 interleaved (13 bit/5 sym)": "#E8590C",
    "two separate arrays": GREY,
}

ENCODING_SHORT = {
    "fp16 dense": "fp16",
    "int8 dense": "int8",
    "TQ1_0 (5 trit/byte)": "TQ1_0",
    "TQ2_0 (2 bit/trit)": "TQ2_0",
    "6-state 3-bit slot": "6-state",
    "Dual6 dual-plane": "Dual6 DP",
    "Dual6 dual-plane (trit-only frame)": "Dual6 trit-only",
    "Dual6 interleaved (13 bit/5 sym)": "Dual6 interleaved",
    "two separate arrays": "two arrays",
}


def chart_scenario_scores():
    """Heat map of the five explicit weight sets, one panel per payload."""
    data = rows("scenario_scores.csv")
    fig, axes = plt.subplots(
        1, 2, figsize=(11.0, 3.4), gridspec_kw={"width_ratios": [9, 6]}, sharey=False
    )
    for ax, payload in zip(axes, ("trit", "dual")):
        subset = [r for r in data if r["payload"] == payload]
        scenarios = []
        for r in subset:
            if r["scenario"] not in scenarios:
                scenarios.append(r["scenario"])
        encodings = sorted(
            {r["encoding"] for r in subset},
            key=lambda e: -max(float(r["weighted_score"]) for r in subset if r["encoding"] == e),
        )
        matrix = []
        for scenario in scenarios:
            line = []
            for encoding in encodings:
                match = [
                    r for r in subset
                    if r["scenario"] == scenario and r["encoding"] == encoding
                ]
                line.append(float(match[0]["weighted_score"]) if match else float("nan"))
            matrix.append(line)
        im = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(encodings)))
        ax.set_xticklabels([ENCODING_SHORT.get(e, e) for e in encodings],
                           rotation=35, ha="right", fontsize=7)
        ax.set_yticks(range(len(scenarios)))
        ax.set_yticklabels(scenarios, fontsize=7.5)
        for i, line in enumerate(matrix):
            for j, value in enumerate(line):
                if math.isnan(value):
                    continue
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=6.5,
                        color="white" if value > 55 else "#212529")
        ax.set_title(f"scenario score, {payload} payload")
        ax.grid(False)
    cbar = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02)
    cbar.set_label("weighted score (0-100)", fontsize=8)
    fig.suptitle("Five weight sets: who wins depends on what you weigh", y=1.02, fontsize=10,
                 fontweight="bold")
    save(fig, "scenario-scores.png")


def chart_bandwidth_crossover():
    """effective_ns = max(compute, bytes/bandwidth), swept over seven links."""
    data = rows("bandwidth_sweep.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), sharey=True)
    for ax, payload in zip(axes, ("trit", "dual")):
        subset = [r for r in data if r["payload"] == payload]
        for encoding in sorted({r["encoding"] for r in subset}):
            pts = sorted(
                (float(r["bandwidth_gbps"]), float(r["effective_ns"]))
                for r in subset if r["encoding"] == encoding
            )
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                "o-",
                ms=3.5,
                lw=1.2,
                color=ENCODING_COLORS.get(encoding, "#868E96"),
                label=ENCODING_SHORT.get(encoding, encoding),
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("bandwidth (GB/s, log)")
        ax.set_title(f"{payload} payload")
        ax.axhline(0.035, color="#333", lw=0.8, ls=":")
    axes[0].set_ylabel("effective ns / element (log)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=9, frameon=False,
               fontsize=6.2, bbox_to_anchor=(0.5, -0.08))
    fig.suptitle("Physical cost model: storage dominates on slow links, compute on fast ones",
                 y=1.02, fontsize=10, fontweight="bold")
    save(fig, "bandwidth-crossover.png")




def chart_weight_sensitivity():
    """Win shares under random weights, plus one-dimensional flip sweeps."""
    sens = rows("weight_sensitivity.csv")
    sweeps = rows("weight_sweeps.csv")
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 6.6))

    for ax, payload in zip(axes[0], ("trit", "dual")):
        subset = [r for r in sens if r["payload"] == payload and r["scheme"] == "s1"]
        subset.sort(key=lambda r: -float(r["share"]))
        subset = [r for r in subset if float(r["share"]) > 0.001][:6]
        labels = [ENCODING_SHORT.get(r["encoding"], r["encoding"]) for r in subset]
        shares = [float(r["share"]) * 100 for r in subset]
        colors = [ENCODING_COLORS.get(r["encoding"], GREY) for r in subset]
        ax.barh(range(len(labels)), shares, color=colors)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7.5)
        ax.invert_yaxis()
        ax.set_xlabel("win share under pseudo-random weights (%)")
        ax.set_title(f"{payload} payload")
        for i, share in enumerate(shares):
            ax.text(share + 0.5, i, f"{share:.1f}%", va="center", fontsize=7)

    for ax, (payload, analysis) in zip(
        axes[1],
        (("trit", "structural"), ("dual", "selective")),
    ):
        subset = [r for r in sweeps if r["payload"] == payload and r["analysis"] == analysis]
        encodings = sorted({r["encoding"] for r in subset})
        top = sorted(
            encodings,
            key=lambda e: -max(float(r["score"]) for r in subset if r["encoding"] == e),
        )[:3]
        for encoding in top:
            pts = sorted(
                (float(r["parameter"]), float(r["score"]))
                for r in subset if r["encoding"] == encoding
            )
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                "o-",
                ms=3,
                lw=1.4,
                color=ENCODING_COLORS.get(encoding, GREY),
                label=ENCODING_SHORT.get(encoding, encoding),
            )
        ax.set_xlabel(f"{analysis} weight (%)")
        ax.set_ylabel("score (0-100)")
        ax.set_title(f"{payload} payload: {analysis} sweep")
        ax.legend(frameon=False, fontsize=7)

    fig.suptitle("Weight sensitivity: the winner depends on what you weigh",
                 y=1.01, fontsize=10, fontweight="bold")
    save(fig, "weight-sensitivity.png")



def chart_composite_scores():
    """Equal-weight comprehensive score, one panel per payload."""
    data = rows("composite_scores.csv")
    proxy = rows("xs_scores.csv")
    fig, axes = plt.subplots(
        1, 3, figsize=(12.0, 3.6), sharex=False,
        gridspec_kw={"width_ratios": [9, 6, 3]},
    )
    panels = (
        (axes[0], "trit", "T payload (trit-only)"),
        (axes[1], "dual", "I payload (independent pair)"),
    )
    for ax, payload, title in panels:
        subset = sorted(
            (r for r in data if r["payload"] == payload),
            key=lambda r: float(r["composite_score"]),
        )
        labels = [ENCODING_SHORT.get(r["encoding"], r["encoding"]) for r in subset]
        scores = [float(r["composite_score"]) for r in subset]
        colors = [ENCODING_COLORS.get(r["encoding"], GREY) for r in subset]
        ax.barh(range(len(labels)), scores, color=colors)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xlim(0, 100)
        ax.set_xlabel("equal-weight composite score (0-100)")
        ax.set_title(title)
        for i, score in enumerate(scores):
            ax.text(score + 1, i, f"{score:.1f}", va="center", fontsize=6.5)
    ax = axes[2]
    labels = ["S shadow", "X exact"]
    scores = [float(r["composite_score"]) for r in sorted(proxy, key=lambda r: float(r["composite_score"]))]
    ax.barh(range(len(labels)), scores, color=[PURPLE, BAD], hatch="//", edgecolor="white")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlim(0, 100)
    ax.set_xlabel("mixed score")
    ax.set_title("X/S (measured decode)")
    for i, score in enumerate(scores):
        ax.text(score + 1, i, f"{score:.1f}", va="center", fontsize=6.5)
    fig.suptitle("All encodings in one score: nine metrics + information utilization",
                 y=1.02, fontsize=10, fontweight="bold")
    save(fig, "composite-scores.png")



def chart_information_budget():
    """Information vs storage for the T / I / X / S data models."""
    data = rows("information_budget.csv")
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    x = list(range(len(data)))
    info = [float(r["info_bits_per_element"]) for r in data]
    storage = [float(r["dual6_storage_bits_per_element"]) for r in data]
    ax.bar([i - 0.2 for i in x], storage, width=0.4, color=GREY, label="Dual6 storage")
    ax.bar([i + 0.2 for i in x], info, width=0.4, color=D6, label="information")
    for i, (inf, sto) in enumerate(zip(info, storage)):
        ax.text(i, max(inf, sto) + 0.05, f"{inf / sto * 100:.0f}% used",
                ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['data_model']} {r['name']}" for r in data], fontsize=7.5)
    ax.set_ylabel("bits per element")
    ax.set_title("Dual6 is optimal only when the two channels are independent")
    ax.legend(frameon=False, fontsize=7.5)
    save(fig, "information-budget.png")

def main():
    chart_scorecard()
    chart_sparse_plane()
    chart_mask_structure()
    chart_fault_size()
    chart_scenario_scores()
    chart_bandwidth_crossover()
    chart_weight_sensitivity()
    chart_composite_scores()
    chart_information_budget()


if __name__ == "__main__":
    main()
