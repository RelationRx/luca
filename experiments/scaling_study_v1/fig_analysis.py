#!/usr/bin/env python3
"""
Targeted analysis figures for scaling_study_v1.

Four panels, each supporting a specific claim:
  A. Over-exploration at 1.5× causes diagnosis failures (experiments run vs diag score)
  B. Rescue is decoupled from diagnosis (diag_score vs rescue_frac scatter)
  C. Prediction accuracy is the clearest budget signal (pred_acc vs budget_mult)
  D. Agent self-terminates early when given excess budget (efficiency vs budget_mult)

Saves: fig_analysis.png
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

STUDY_DIR = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

N_GENES  = [10, 15, 20]
BUDGETS  = [0.5, 1.0, 1.5]

# ── Palette ─────────────────────────────────────────────────────────────────
DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
GRID_C   = "#21262d"
TEXT_C   = "#e6edf3"
MUT_C    = "#8b949e"

GREEN  = "#3fb950"
BLUE   = "#58a6ff"
YELLOW = "#d29922"
RED    = "#f85149"
PURPLE = "#bc8cff"

COLORS_N = {10: BLUE, 15: GREEN, 20: YELLOW}
COLORS_B = {0.5: "#58a6ff", 1.0: "#3fb950", 1.5: "#f85149"}

plt.rcParams.update({
    "figure.facecolor": DARK_BG,
    "axes.facecolor":   PANEL_BG,
    "axes.edgecolor":   GRID_C,
    "axes.labelcolor":  TEXT_C,
    "xtick.color":      TEXT_C,
    "ytick.color":      TEXT_C,
    "text.color":       TEXT_C,
    "grid.color":       GRID_C,
    "grid.linewidth":   0.6,
    "font.family":      "monospace",
    "font.size":        10,
    "axes.titlesize":   11,
    "axes.titleweight": "bold",
})


def load():
    return [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]


def mean_or_nan(vals):
    v = [x for x in vals if x is not None]
    return statistics.mean(v) if v else float("nan")


def std_or_nan(vals):
    v = [x for x in vals if x is not None]
    return statistics.stdev(v) if len(v) > 1 else 0.0


# ── Panel A: Over-exploration —— experiments run vs diag score ───────────────
def panel_A(ax, records):
    """
    Strip chart: x = budget_multiplier (jittered by n_genes),
                 y = n_experiments,    colour = diag_score (green / red).
    Annotate the two failure cases.
    """
    jitter = {10: -0.08, 15: 0.0, 20: 0.08}
    marker = {10: "o", 15: "s", 20: "^"}

    for r in records:
        n   = r["n_genes"]
        bm  = r["budget_multiplier"]
        ne  = r["n_experiments"]
        sc  = r["malfunction_score"] if r["malfunction_score"] is not None else -1
        col = GREEN if sc == 1.0 else (YELLOW if sc == 0.5 else RED)
        ec  = "white" if sc == 1.0 else RED

        ax.scatter(bm + jitter[n], ne,
                   color=col, marker=marker[n], s=90,
                   edgecolors=ec, linewidth=1.0, zorder=4)

        # annotate failures
        if sc < 1.0:
            ax.annotate(
                f"diag=0\nn={n}/s{r['seed']}",
                xy=(bm + jitter[n], ne),
                xytext=(bm + jitter[n] + 0.14, ne + 1.5),
                fontsize=7.5, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=0.8),
            )

    # horizontal reference lines: budget_total for each (n, mult)
    for n in N_GENES:
        for bm in BUDGETS:
            rs = [r for r in records if r["n_genes"] == n
                  and abs(r["budget_multiplier"] - bm) < 1e-9]
            bt = rs[0]["budget_total"] if rs else None
            if bt:
                ax.hlines(bt, bm + jitter[n] - 0.05, bm + jitter[n] + 0.05,
                          colors=COLORS_N[n], linewidths=1.2,
                          linestyles="--", alpha=0.5, zorder=2)

    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Experiments run")
    ax.set_title("A.  Over-exploration at 1.5× budget")
    ax.grid(True, axis="y", alpha=0.5)

    # legend
    leg_n = [mlines.Line2D([], [], marker=marker[n], color="w",
                           markerfacecolor=COLORS_N[n], markersize=8, label=f"n={n}")
             for n in N_GENES]
    leg_sc = [mpatches.Patch(color=GREEN, label="diag = 1.0"),
              mpatches.Patch(color=RED,   label="diag = 0.0")]
    ax.legend(handles=leg_n + leg_sc, fontsize=8, ncol=2,
              framealpha=0.3, facecolor=PANEL_BG)
    ax.text(0.97, 0.04, "dashed = budget total",
            transform=ax.transAxes, ha="right", fontsize=7, color=MUT_C)


# ── Panel B: Rescue decoupled from diagnosis ─────────────────────────────────
def panel_B(ax, records):
    """
    Scatter: x = diag_score (jittered), y = rescue_frac.
    Colour = n_genes. Red dashed box around the failure-but-rescued region.
    """
    jitter_d = {0.0: -0.04, 0.5: 0.0, 1.0: 0.04}

    for r in records:
        sc = r["malfunction_score"]
        rf = r["best_rescue_fraction"]
        n  = r["n_genes"]
        bm = r["budget_multiplier"]
        if sc is None:
            continue
        jx = jitter_d.get(sc, 0) + np.random.default_rng(
            int(r["seed"] * 13 + r["n_genes"])).uniform(-0.015, 0.015)
        jy = np.random.default_rng(
            int(r["seed"] * 7 + int(bm * 10))).uniform(-0.008, 0.008)
        y = rf + jy if rf is not None else -0.05

        ax.scatter(sc + jx, y,
                   color=COLORS_N[n], marker="o" if bm == 1.0 else ("^" if bm == 0.5 else "s"),
                   s=80, edgecolors="white", linewidth=0.4, zorder=4,
                   alpha=0.88)

    # highlight decoupling region: diag=0, rescue=1.0
    rect = mpatches.FancyBboxPatch(
        (-0.12, 0.88), 0.30, 0.16,
        boxstyle="round,pad=0.01",
        linewidth=1.5, edgecolor=RED, facecolor="none",
        linestyle="--", zorder=5,
    )
    ax.add_patch(rect)
    ax.text(-0.02, 0.87, "failed diagnosis,\nsuccessful rescue",
            fontsize=7.5, color=RED, va="top", ha="center")

    ax.set_xlim(-0.2, 1.15)
    ax.set_ylim(-0.12, 1.08)
    ax.set_xticks([0.0, 0.5, 1.0])
    ax.set_xticklabels(["0.0\n(wrong)", "0.5\n(partial)", "1.0\n(exact)"])
    ax.set_xlabel("Diagnosis score")
    ax.set_ylabel("Best rescue fraction")
    ax.set_title("B.  Rescue decoupled from diagnosis")
    ax.axhline(1.0, color=GRID_C, linewidth=0.8, linestyle=":")
    ax.grid(True, alpha=0.4)

    leg_n = [mlines.Line2D([], [], marker="o", color="w",
                           markerfacecolor=COLORS_N[n], markersize=8, label=f"n={n}")
             for n in N_GENES]
    ax.legend(handles=leg_n, fontsize=8, framealpha=0.3, facecolor=PANEL_BG)


# ── Panel C: Prediction accuracy — clearest budget signal ─────────────────────
def panel_C(ax, records):
    """
    Line plot: x = budget_mult, y = mean pred_acc, per n_genes.
    Shaded band = ±1 std.  Individual seed dots jittered.
    Overall mean (all n_genes pooled) as a thick white line.
    """
    jitter_n = {10: -0.04, 15: 0.0, 20: 0.04}
    marker    = {10: "o", 15: "s", 20: "^"}

    overall_means = []
    for bm in BUDGETS:
        vals = [r["avg_prediction_accuracy"] for r in records
                if abs(r["budget_multiplier"] - bm) < 1e-9
                and r["avg_prediction_accuracy"] is not None]
        overall_means.append(mean_or_nan(vals))
    ax.plot(BUDGETS, overall_means, color="white", linewidth=2.5,
            linestyle="--", zorder=5, label="all n (mean)", alpha=0.6)

    for n in N_GENES:
        means, stds = [], []
        for bm in BUDGETS:
            vals = [r["avg_prediction_accuracy"] for r in records
                    if r["n_genes"] == n
                    and abs(r["budget_multiplier"] - bm) < 1e-9
                    and r["avg_prediction_accuracy"] is not None]
            means.append(mean_or_nan(vals))
            stds.append(std_or_nan(vals))

        ma = np.array(means, dtype=float)
        sa = np.array(stds,  dtype=float)
        c  = COLORS_N[n]

        ax.plot(BUDGETS, ma, color=c, marker=marker[n],
                linewidth=2, markersize=9, zorder=4, label=f"n={n}")
        ax.fill_between(BUDGETS, ma - sa, ma + sa, color=c, alpha=0.15)

        # seed dots
        for bm in BUDGETS:
            vals = [r["avg_prediction_accuracy"] for r in records
                    if r["n_genes"] == n
                    and abs(r["budget_multiplier"] - bm) < 1e-9
                    and r["avg_prediction_accuracy"] is not None]
            jx = jitter_n[n]
            ax.scatter([bm + jx] * len(vals), vals,
                       color=c, s=22, alpha=0.55, zorder=3)

    # delta annotations between 0.5× and 1.5×
    for n in N_GENES:
        vals_lo = [r["avg_prediction_accuracy"] for r in records
                   if r["n_genes"] == n and abs(r["budget_multiplier"] - 0.5) < 1e-9
                   and r["avg_prediction_accuracy"] is not None]
        vals_hi = [r["avg_prediction_accuracy"] for r in records
                   if r["n_genes"] == n and abs(r["budget_multiplier"] - 1.5) < 1e-9
                   and r["avg_prediction_accuracy"] is not None]
        delta = mean_or_nan(vals_hi) - mean_or_nan(vals_lo)
        if not np.isnan(delta) and abs(delta) > 0.001:
            ax.annotate(f"Δ{delta:+.2f}",
                        xy=(1.5, mean_or_nan(vals_hi)),
                        xytext=(1.56, mean_or_nan(vals_hi)),
                        fontsize=7.5, color=COLORS_N[n], va="center")

    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Avg prediction accuracy")
    ax.set_ylim(0.45, 1.12)
    ax.set_title("C.  Prediction: clearest budget scaling signal")
    ax.grid(True, axis="y", alpha=0.5)
    ax.legend(fontsize=8, framealpha=0.3, facecolor=PANEL_BG)


# ── Panel D: Agent self-terminates — efficiency vs budget ─────────────────────
def panel_D(ax, records):
    """
    Line plot: x = budget_mult, y = budget_used/budget_total (mean ± std).
    Per n_genes. Annotate that efficiency drops because the agent stops early.
    """
    marker = {10: "o", 15: "s", 20: "^"}

    for n in N_GENES:
        means, stds = [], []
        for bm in BUDGETS:
            vals = [r["budget_used"] / r["budget_total"]
                    for r in records
                    if r["n_genes"] == n
                    and abs(r["budget_multiplier"] - bm) < 1e-9
                    and r["budget_total"]]
            means.append(mean_or_nan(vals))
            stds.append(std_or_nan(vals))

        ma = np.array(means, dtype=float)
        sa = np.array(stds,  dtype=float)
        c  = COLORS_N[n]

        ax.plot(BUDGETS, ma, color=c, marker=marker[n],
                linewidth=2, markersize=9, zorder=4, label=f"n={n}")
        ax.fill_between(BUDGETS, ma - sa, ma + sa, color=c, alpha=0.15)

        # seed dots
        jitter_n = {10: -0.04, 15: 0.0, 20: 0.04}
        for bm in BUDGETS:
            vals = [r["budget_used"] / r["budget_total"]
                    for r in records
                    if r["n_genes"] == n
                    and abs(r["budget_multiplier"] - bm) < 1e-9
                    and r["budget_total"]]
            ax.scatter([bm + jitter_n[n]] * len(vals), vals,
                       color=c, s=22, alpha=0.55, zorder=3)

    # Annotation: "agent stops early — remaining budget unused"
    ax.annotate(
        "agent stops early;\nexcess budget unused",
        xy=(1.5, 0.66), xytext=(1.2, 0.52),
        fontsize=8, color=MUT_C,
        arrowprops=dict(arrowstyle="->", color=MUT_C, lw=0.9),
    )
    ax.axhline(1.0, color=GRID_C, linewidth=0.8, linestyle=":",
               label="100% used", alpha=0.7)

    ax.set_xticks(BUDGETS)
    ax.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec)", "1.5×\n(generous)"])
    ax.set_xlabel("Budget multiplier")
    ax.set_ylabel("Budget efficiency  (used / total)")
    ax.set_ylim(0.35, 1.10)
    ax.set_title("D.  Agent self-terminates with excess budget")
    ax.grid(True, axis="y", alpha=0.5)
    ax.legend(fontsize=8, framealpha=0.3, facecolor=PANEL_BG)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    records = load()
    print(f"[fig_analysis] {len(records)} records loaded")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "Scaling Study v1 — Analysis Support Figures",
        fontsize=14, fontweight="bold", y=1.01,
    )

    panel_A(axes[0, 0], records)
    panel_B(axes[0, 1], records)
    panel_C(axes[1, 0], records)
    panel_D(axes[1, 1], records)

    fig.tight_layout(h_pad=3.5, w_pad=3.0)
    out = STUDY_DIR / "fig_analysis.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"[fig_analysis] saved → {out.name}")
    plt.close(fig)


if __name__ == "__main__":
    main()
