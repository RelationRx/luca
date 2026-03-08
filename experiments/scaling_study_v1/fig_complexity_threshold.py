#!/usr/bin/env python3
"""
Complexity scaling figure — how the dissociation pattern shifts with n_genes.

Three panels:
  A  Diagnosis score vs budget, all n_genes  (threshold shifts right at n=35)
  B  Prediction accuracy vs budget, all n_genes  (flat — budget-insensitive)
  C  Budget threshold vs n_genes  (minimum multiplier for reliable diagnosis)

n=35 is marked as preliminary (1 seed only).
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np

STUDY_DIR    = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

BUDGETS = [0.5, 1.0, 1.5]

# n=35 has only 1 seed — flag it visually
N_SEEDS     = {10: 3, 15: 3, 20: 3, 35: 1}
N_COLORS    = {10: "#3b82f6", 15: "#10b981", 20: "#f59e0b", 35: "#ef4444"}
N_MARKERS   = {10: "o",       15: "s",       20: "^",       35: "D"}

TXT  = "#0f172a"
SUB  = "#64748b"
PROV = "#94a3b8"

plt.rcParams.update({
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
    "axes.edgecolor":    "#cbd5e1",
    "axes.labelcolor":   TXT,
    "xtick.color":       SUB,
    "ytick.color":       SUB,
    "text.color":        TXT,
    "grid.color":        "#e2e8f0",
    "grid.linewidth":    0.7,
    "font.family":       "sans-serif",
    "font.size":         10.5,
    "axes.titlesize":    12,
    "axes.titleweight":  "bold",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.direction":   "out",
    "ytick.direction":   "out",
})


def load():
    return [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]


def cell(records, metric, n, m):
    vals = [r[metric] for r in records
            if r["n_genes"] == n and abs(r["budget_multiplier"] - m) < 1e-9
            and r[metric] is not None]
    if not vals:
        return float("nan"), float("nan")
    mean = statistics.mean(vals)
    std  = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return mean, std


def n_genes_levels(records):
    return sorted({r["n_genes"] for r in records})


# ─── Panel A: Diagnosis score vs budget ──────────────────────────────────────
def panel_A(ax, records):
    ns = n_genes_levels(records)
    xs = np.array(BUDGETS)

    for n in ns:
        col = N_COLORS[n]; mk = N_MARKERS[n]
        prelim = N_SEEDS[n] == 1
        ls = "--" if prelim else "-"
        lw = 1.8 if prelim else 2.5
        ms = 7  if prelim else 8

        means = np.array([cell(records, "malfunction_score", n, m)[0] for m in BUDGETS])
        stds  = np.array([cell(records, "malfunction_score", n, m)[1] for m in BUDGETS])

        ax.plot(xs, means, color=col, lw=lw, ls=ls,
                marker=mk, markersize=ms,
                markerfacecolor="white" if prelim else col,
                markeredgewidth=2.0 if prelim else 1.0,
                zorder=4, label=f"n={n}{'  †' if prelim else ''}")
        if not prelim:
            ax.fill_between(xs, means - stds, means + stds,
                            color=col, alpha=0.10, zorder=2)

    # Threshold annotation: n=35 fails at 0.5×
    ax.annotate(
        "threshold shifts\nright at n=35",
        xy=(0.5, 0.0), xytext=(0.72, 0.22),
        fontsize=8.5, color=N_COLORS[35],
        arrowprops=dict(arrowstyle="-|>", color=N_COLORS[35], lw=1.1),
    )

    ax.set_xlim(0.35, 1.65)
    ax.set_ylim(-0.08, 1.18)
    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec.)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Diagnosis score")
    ax.set_title("A   Diagnosis score vs budget")
    ax.grid(True, axis="y")
    ax.legend(fontsize=9, frameon=False, loc="lower right")


# ─── Panel B: Prediction accuracy vs budget ───────────────────────────────────
def panel_B(ax, records):
    ns = n_genes_levels(records)
    xs = np.array(BUDGETS)

    for n in ns:
        col = N_COLORS[n]; mk = N_MARKERS[n]
        prelim = N_SEEDS[n] == 1
        ls = "--" if prelim else "-"
        lw = 1.8 if prelim else 2.5

        means = np.array([cell(records, "avg_prediction_accuracy", n, m)[0] for m in BUDGETS])
        stds  = np.array([cell(records, "avg_prediction_accuracy", n, m)[1] for m in BUDGETS])

        ax.plot(xs, means, color=col, lw=lw, ls=ls,
                marker=mk, markersize=7 if prelim else 8,
                markerfacecolor="white" if prelim else col,
                markeredgewidth=2.0 if prelim else 1.0,
                zorder=4, label=f"n={n}{'  †' if prelim else ''}")
        if not prelim:
            ax.fill_between(xs, means - stds, means + stds,
                            color=col, alpha=0.10, zorder=2)

    ax.text(0.97, 0.10, "prediction already\nperfect at 1.0× for all n",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.5, color=SUB, style="italic")

    ax.set_xlim(0.35, 1.65)
    ax.set_ylim(0.55, 1.12)
    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec.)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Prediction accuracy")
    ax.set_title("B   Prediction accuracy vs budget")
    ax.grid(True, axis="y")
    ax.legend(fontsize=9, frameon=False, loc="lower right")


# ─── Panel C: Budget threshold vs n_genes ────────────────────────────────────
def panel_C(ax, records):
    """
    For each n_genes, show the minimum budget multiplier at which
    mean diagnosis score >= 0.8. Encodes the idea that the threshold
    shifts right with complexity.
    """
    ns = n_genes_levels(records)

    thresholds = []
    for n in ns:
        found = None
        for m in sorted(BUDGETS):
            vals = [r["malfunction_score"] for r in records
                    if r["n_genes"] == n and abs(r["budget_multiplier"] - m) < 1e-9
                    and r["malfunction_score"] is not None]
            if vals and statistics.mean(vals) >= 0.8:
                found = m
                break
        thresholds.append(found if found is not None else float("nan"))

    xs = np.arange(len(ns))
    cols   = [N_COLORS[n] for n in ns]
    prelim = [N_SEEDS[n] == 1 for n in ns]

    bars = ax.bar(xs, thresholds, color=cols, alpha=0.80,
                  edgecolor=cols, linewidth=1.8, width=0.55, zorder=3)

    # Hatch the preliminary bars
    for bar, p in zip(bars, prelim):
        if p:
            bar.set_hatch("///")
            bar.set_alpha(0.55)

    # Value labels
    for x, t, p in zip(xs, thresholds, prelim):
        if not np.isnan(t):
            ax.text(x, t + 0.025, f"{t:.1f}×{'†' if p else ''}",
                    ha="center", va="bottom", fontsize=10,
                    fontweight="bold",
                    color=N_COLORS[ns[int(x)]])

    # Trend arrow
    valid = [(x, t) for x, t in zip(xs, thresholds) if not np.isnan(t)]
    if len(valid) >= 2:
        x0, t0 = valid[0]; xn, tn = valid[-1]
        if tn > t0:
            ax.annotate("", xy=(xn + 0.05, tn + 0.06),
                        xytext=(x0 - 0.05, t0 + 0.06),
                        arrowprops=dict(arrowstyle="-|>", color="#64748b",
                                        lw=1.4, connectionstyle="arc3,rad=-0.2"))
            ax.text((x0 + xn) / 2, max(thresholds) + 0.14,
                    "threshold rises\nwith complexity",
                    ha="center", va="bottom", fontsize=9,
                    color=SUB, style="italic")

    ax.set_xticks(xs)
    ax.set_xticklabels([f"n={n}" for n in ns])
    ax.set_ylim(0, 1.75)
    ax.set_yticks(BUDGETS)
    ax.set_yticklabels(["0.5×\n(tight)", "1.0×\n(rec.)", "1.5×\n(generous)"])
    ax.set_xlabel("Network size (n genes)")
    ax.set_ylabel("Min. budget for diagnosis ≥ 0.8")
    ax.set_title("C   Budget threshold vs complexity")
    ax.grid(True, axis="y")

    # Hatch legend
    ax.legend(handles=[
        mpatches.FancyBboxPatch((0, 0), 1, 1,
            boxstyle="square,pad=0", facecolor="#cccccc",
            hatch="///", edgecolor="#888", alpha=0.55,
            label="† 1 seed (preliminary)"),
    ], fontsize=8.5, frameon=False, loc="upper left")


# ─── Assemble ─────────────────────────────────────────────────────────────────
def main():
    records = load()
    ns = n_genes_levels(records)
    seed_counts = {n: len({r["seed"] for r in records if r["n_genes"] == n}) for n in ns}
    print(f"[complexity_fig] {len(records)} records  |  "
          + "  ".join(f"n={n}:{seed_counts[n]}seeds" for n in ns))

    fig = plt.figure(figsize=(15, 5.5))
    gs = fig.add_gridspec(
        1, 3,
        width_ratios=[1.0, 1.0, 0.85],
        left=0.07, right=0.97,
        bottom=0.15, top=0.82,
        wspace=0.38,
    )
    ax_A = fig.add_subplot(gs[0])
    ax_B = fig.add_subplot(gs[1])
    ax_C = fig.add_subplot(gs[2])

    panel_A(ax_A, records)
    panel_B(ax_B, records)
    panel_C(ax_C, records)

    fig.text(0.5, 0.97,
             "Dissociation pattern extends to higher complexity",
             ha="center", va="top", fontsize=13, fontweight="bold", color=TXT)
    fig.text(0.5, 0.925,
             "Diagnosis budget threshold rises with n — prediction stays robust  "
             "  (dashed / hatched = n=35, 1 seed, preliminary)",
             ha="center", va="top", fontsize=9.5, color=PROV, style="italic")

    out = STUDY_DIR / "fig_complexity_threshold.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"[complexity_fig] saved → {out.name}")
    plt.close(fig)


if __name__ == "__main__":
    main()
