#!/usr/bin/env python3
"""
Mock main figure for the LUCA paper.

Central claim: diagnosis and prediction dissociate under budget constraints.
  • Recognition tasks (diagnosis, rescue) are flat — budget-insensitive.
  • Generalisation tasks (prediction) rise monotonically with budget.
  • Exception: over-generous budget causes over-exploration failures at n=20.

Layout: 3 panels
  A  Diagnosis + rescue vs budget  (flat — "recognition")
  B  Prediction accuracy vs budget  (rising — "generalisation")
  C  Schematic explanation of the dissociation
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines  as mlines
import matplotlib.patheffects as pe
import numpy as np

STUDY_DIR    = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

N_GENES = [10, 15, 20]
BUDGETS = [0.5, 1.0, 1.5]

# ── Publication palette (colorblind-safe) ────────────────────────────────────
COL_DIAG    = "#1f77b4"   # blue
COL_RESCUE  = "#2ca02c"   # green
COL_PRED    = "#d62728"   # red
COL_POOLED  = "#333333"   # near-black for pooled mean
GREY_BAND   = "#cccccc"

N_COLORS    = {10: "#4393c3", 15: "#74c476", 20: "#fd8d3c"}   # cool → warm

plt.rcParams.update({
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
    "axes.edgecolor":    "#333333",
    "axes.labelcolor":   "#333333",
    "xtick.color":       "#333333",
    "ytick.color":       "#333333",
    "text.color":        "#333333",
    "grid.color":        "#e0e0e0",
    "grid.linewidth":    0.7,
    "font.family":       "sans-serif",
    "font.size":         9.5,
    "axes.titlesize":    10.5,
    "axes.titleweight":  "bold",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.direction":   "out",
    "ytick.direction":   "out",
})


def load():
    return [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]


def stats(records, metric, n, m):
    vals = [r[metric] for r in records
            if r["n_genes"] == n and abs(r["budget_multiplier"] - m) < 1e-9
            and r[metric] is not None]
    if not vals:
        return float("nan"), 0.0
    return statistics.mean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


def pooled_stats(records, metric, m):
    vals = [r[metric] for r in records
            if abs(r["budget_multiplier"] - m) < 1e-9 and r[metric] is not None]
    if not vals:
        return float("nan"), 0.0
    return statistics.mean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


# ── Panel A: recognition (flat) ──────────────────────────────────────────────
def panel_A(ax, records):
    xs = np.array(BUDGETS)

    for metric, color, label, ls in [
        ("malfunction_score",    COL_DIAG,   "Diagnosis score",   "-"),
        ("best_rescue_fraction", COL_RESCUE, "Best rescue frac",  "--"),
    ]:
        means = np.array([pooled_stats(records, metric, m)[0] for m in BUDGETS])
        stds  = np.array([pooled_stats(records, metric, m)[1] for m in BUDGETS])

        ax.plot(xs, means, color=color, linewidth=2.5, linestyle=ls,
                marker="o", markersize=7, label=label, zorder=4)
        ax.fill_between(xs, means - stds, means + stds,
                        color=color, alpha=0.12, zorder=2)

        # Per-n_genes thin lines
        for n in N_GENES:
            mn = np.array([stats(records, metric, n, m)[0] for m in BUDGETS])
            ax.plot(xs, mn, color=color, linewidth=0.8, linestyle=ls,
                    alpha=0.35, zorder=3)

    # Annotate the n=20 diagnosis dip
    ax.annotate(
        "over-exploration\nfailures (n=20)",
        xy=(1.5, 0.333), xytext=(1.28, 0.48),
        fontsize=8, color=COL_DIAG,
        arrowprops=dict(arrowstyle="-|>", color=COL_DIAG,
                        lw=1.0, connectionstyle="arc3,rad=-0.2"),
    )

    ax.set_xlim(0.35, 1.65)
    ax.set_ylim(-0.02, 1.18)
    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec.)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Score")
    ax.set_title("A   Recognition tasks")
    ax.grid(True, axis="y")
    ax.legend(fontsize=8.5, frameon=False, loc="lower left")

    # "flat" callout
    ax.text(0.98, 0.88, "robust across\nall budgets",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8, color="#666666", style="italic")


# ── Panel B: generalisation (rising) ─────────────────────────────────────────
def panel_B(ax, records):
    xs = np.array(BUDGETS)

    # Per-n_genes lines (thin, colour-coded)
    for n in N_GENES:
        mn = np.array([stats(records, "avg_prediction_accuracy", n, m)[0] for m in BUDGETS])
        ax.plot(xs, mn, color=N_COLORS[n], linewidth=1.2,
                marker="o", markersize=5, alpha=0.55, zorder=3)

    # Pooled mean (thick)
    means = np.array([pooled_stats(records, "avg_prediction_accuracy", m)[0] for m in BUDGETS])
    stds  = np.array([pooled_stats(records, "avg_prediction_accuracy", m)[1] for m in BUDGETS])

    ax.plot(xs, means, color=COL_PRED, linewidth=2.8,
            marker="o", markersize=8, label="Pooled mean", zorder=5)
    ax.fill_between(xs, means - stds, means + stds,
                    color=COL_PRED, alpha=0.12, zorder=2)

    # Δ annotation (0.5× → 1.5×)
    delta = means[-1] - means[0]
    mid_x = 1.0
    mid_y = (means[0] + means[-1]) / 2
    ax.annotate("", xy=(1.5, means[-1] - 0.01), xytext=(1.5, means[0] + 0.01),
                arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.3))
    ax.text(1.54, mid_y, f"Δ = {delta:+.2f}", va="center",
            fontsize=8.5, color="#555555", fontweight="bold")

    # Budget threshold annotation at 1.0×
    ax.axvline(1.0, color="#aaaaaa", linewidth=0.9, linestyle=":",
               zorder=1)
    ax.text(1.01, 0.52, "recommended\nbudget", fontsize=7.5,
            color="#aaaaaa", va="bottom")

    ax.set_xlim(0.35, 1.75)
    ax.set_ylim(0.50, 1.12)
    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec.)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Prediction accuracy")
    ax.set_title("B   Generalisation task")
    ax.grid(True, axis="y")

    # n_genes legend
    leg_n = [mlines.Line2D([], [], color=N_COLORS[n], linewidth=1.5,
                           marker="o", markersize=5, label=f"n={n} genes")
             for n in N_GENES]
    leg_p = [mlines.Line2D([], [], color=COL_PRED, linewidth=2.5,
                           marker="o", markersize=7, label="Pooled mean")]
    ax.legend(handles=leg_n + leg_p, fontsize=8, frameon=False, loc="lower right")


# ── Panel C: schematic explanation ───────────────────────────────────────────
def panel_C(ax):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def box(cx, cy, w, h, color, alpha=0.15, lw=1.5, ls="-"):
        r = mpatches.FancyBboxPatch(
            (cx - w/2, cy - h/2), w, h,
            boxstyle="round,pad=0.15",
            facecolor=color, alpha=alpha,
            edgecolor=color, linewidth=lw, linestyle=ls,
        )
        ax.add_patch(r)

    def arrow(x1, y1, x2, y2, color="#555555", lw=1.4, style="->"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle=style, color=color,
                                   lw=lw, connectionstyle="arc3,rad=0.0"))

    def txt(x, y, s, **kw):
        ax.text(x, y, s, ha="center", va="center",
                fontsize=kw.pop("fs", 9), **kw)

    # ── Title ──
    txt(5, 9.5, "C   Why the metrics dissociate", fs=10.5, fontweight="bold")

    # ── Experiment box ──
    box(2, 7.6, 3.0, 1.2, "#1f77b4")
    txt(2, 7.6, "Perturbation\nexperiments\n(budget-limited)", fs=8.5)

    # ── Two downstream paths ──
    arrow(3.5, 7.9, 4.9, 8.8, "#1f77b4")   # → diagnosis
    arrow(3.5, 7.3, 4.9, 6.3, COL_PRED)    # → prediction

    # ── Diagnosis path ──
    box(6.5, 8.9, 3.2, 1.1, COL_DIAG)
    txt(6.5, 9.25, "Identify fault", fs=8.5, fontweight="bold", color=COL_DIAG)
    txt(6.5, 8.7, "few targeted experiments\nsuffice → budget-insensitive",
        fs=7.5, color="#444444")

    box(6.5, 7.5, 3.2, 1.0, COL_RESCUE)
    txt(6.5, 7.85, "Rescue phenotype", fs=8.5, fontweight="bold", color=COL_RESCUE)
    txt(6.5, 7.4, "empirical search; decoupled\nfrom diagnosis",
        fs=7.5, color="#444444")

    # ── Prediction path ──
    box(6.5, 5.8, 3.2, 1.3, COL_PRED)
    txt(6.5, 6.15, "Predict novel\ncombinations", fs=8.5, fontweight="bold",
        color=COL_PRED)
    txt(6.5, 5.62, "needs full causal model\n→  budget-sensitive",
        fs=7.5, color="#444444")

    # ── "flat" vs "rising" side labels ──
    txt(9.55, 8.3, "flat\n≈ 1.0", fs=8, color="#888888", style="italic")
    ax.annotate("", xy=(9.1, 5.6), xytext=(9.1, 7.2),
                arrowprops=dict(arrowstyle="-|>", color=COL_PRED, lw=1.3))
    txt(9.6, 6.4, "rises\nwith\nbudget", fs=8, color=COL_PRED, fontweight="bold")

    # ── Over-exploration failure callout ──
    box(2, 4.5, 3.2, 1.5, "#d62728", alpha=0.07, lw=1.2, ls="--")
    txt(2, 4.9, "⚠  Over-exploration", fs=8.2, color="#d62728", fontweight="bold")
    txt(2, 4.35, "excess budget (1.5×) at n=20\ncauses unfocused search;\ndiagnosis regresses",
        fs=7.5, color="#555555")
    arrow(3.5, 5.0, 4.9, 7.3, "#d62728", lw=1.0, style="-|>")


# ── Assemble ─────────────────────────────────────────────────────────────────
def main():
    records = load()
    print(f"[paper_fig] {len(records)} records")

    fig = plt.figure(figsize=(14, 5.8))

    # Two data panels (A, B) and one schematic (C)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.15, 1.4],
                          left=0.06, right=0.97, bottom=0.14, top=0.82,
                          wspace=0.38)

    ax_A = fig.add_subplot(gs[0])
    ax_B = fig.add_subplot(gs[1])
    ax_C = fig.add_subplot(gs[2])

    panel_A(ax_A, records)
    panel_B(ax_B, records)
    panel_C(ax_C)

    # Shared super-title
    fig.text(0.5, 0.98,
             "Diagnosis and prediction dissociate under budget constraints",
             ha="center", va="top", fontsize=12, fontweight="bold",
             color="#111111")
    fig.text(0.5, 0.935,
             "LLMs are robust causal diagnosers but budget-limited causal modellers",
             ha="center", va="top", fontsize=9.5, color="#555555",
             style="italic")

    out = STUDY_DIR / "fig_paper_main.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"[paper_fig] saved → {out.name}")
    plt.close(fig)


if __name__ == "__main__":
    main()
