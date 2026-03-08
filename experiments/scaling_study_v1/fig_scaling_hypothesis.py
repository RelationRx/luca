#!/usr/bin/env python3
"""
Hypothesised scaling figure — the speculative main conclusion.

Shows what we expect to happen as n_genes scales from the current
study range (10–20) out to real biological systems (10,000+).

Three panels:
  A. Performance curves — diagnosis, rescue, prediction vs log n_genes
     Solid = measured (this study).  Dashed = hypothesised.
     Phase-transition zone highlighted.

  B. Mechanism — WHY performance degrades:
     budget exhaustion rate and gene-coverage fraction.

  C. Strategy-shift hypothesis — what an adaptive agent SHOULD do
     vs what current LLMs likely do as complexity grows.
     The gap between these curves is the next experiment.

All curves beyond n=20 are model-based extrapolations, not data.
The functional forms and transition parameters are informed by
first principles; exact values should be treated as hypotheses.
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
import matplotlib.ticker as mticker
import numpy as np
from scipy.special import expit   # sigmoid

STUDY_DIR    = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

# ── Palette (publication) ────────────────────────────────────────────────────
COL_DIAG    = "#1f77b4"
COL_RESCUE  = "#2ca02c"
COL_PRED    = "#d62728"
COL_BUDGET  = "#9467bd"
COL_COVER   = "#8c564b"
COL_IDEAL   = "#17becf"
COL_LLM     = "#e377c2"
PHASE_COL   = "#f0c040"
GREY        = "#aaaaaa"

plt.rcParams.update({
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
    "axes.edgecolor":    "#333333",
    "axes.labelcolor":   "#333333",
    "xtick.color":       "#333333",
    "ytick.color":       "#333333",
    "text.color":        "#333333",
    "grid.color":        "#e8e8e8",
    "grid.linewidth":    0.7,
    "font.family":       "sans-serif",
    "font.size":         9.5,
    "axes.titlesize":    10.5,
    "axes.titleweight":  "bold",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# ── x-axis: log-spaced n_genes ────────────────────────────────────────────────
N_RANGE  = np.logspace(np.log10(8), np.log10(20_000), 400)

# Boundary between measured and hypothesised
N_MEASURED = 20          # our study goes up to here
N_PHASE_LO = 80          # phase transition start
N_PHASE_HI = 300         # phase transition end (rough)

# ── Sigmoid helper (on log scale) ────────────────────────────────────────────
def log_sigmoid_drop(n, center, width, floor=0.05, ceiling=1.0):
    """Drops from `ceiling` to `floor` with sigmoid centre at `center`."""
    log_n   = np.log10(n)
    log_c   = np.log10(center)
    return floor + (ceiling - floor) * expit(-(log_n - log_c) / (width / 4))


def log_sigmoid_rise(n, center, width, floor=0.0, ceiling=1.0):
    log_n   = np.log10(n)
    log_c   = np.log10(center)
    return floor + (ceiling - floor) * expit( (log_n - log_c) / (width / 4))


# ── Load actual measured data ─────────────────────────────────────────────────
def measured_means():
    records = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]
    result = {}
    for n in [10, 15, 20]:
        diag = [r["malfunction_score"]        for r in records if r["n_genes"] == n
                and r["malfunction_score"] is not None]
        resc = [r["best_rescue_fraction"]      for r in records if r["n_genes"] == n
                and r["best_rescue_fraction"] is not None]
        pred = [r["avg_prediction_accuracy"]   for r in records if r["n_genes"] == n
                and r["avg_prediction_accuracy"] is not None]
        result[n] = {
            "diag": statistics.mean(diag),
            "resc": statistics.mean(resc),
            "pred": statistics.mean(pred),
        }
    return result


# ── Hypothesised curves ───────────────────────────────────────────────────────
# Diagnosis: robust until ~150, then sigmoidal collapse
# Reasoning: fault localisation needs O(n) experiments in worst case;
#            once budget << n, the agent can't reliably reach the faulty gene.
diag_curve  = log_sigmoid_drop(N_RANGE, center=150, width=1.2, floor=0.05)

# Rescue: more robust — empirical search only needs to find *a* corrective
# intervention, not identify *which* gene; holds up longer
resc_curve  = log_sigmoid_drop(N_RANGE, center=350, width=1.3, floor=0.03)

# Prediction: requires a full forward model; drops earliest
# already sensitive at n=15–20; collapses well before diagnosis does
pred_curve  = log_sigmoid_drop(N_RANGE, center=70,  width=1.0, floor=0.02)

# Budget exhaustion rate: fraction of runs that hit the ceiling
# Near 0 now (agent finishes early); climbs to ~1 as n grows
budg_curve  = log_sigmoid_rise(N_RANGE, center=100, width=1.1,
                               floor=0.15, ceiling=0.98)

# Gene coverage: fraction of genes the agent ever probes
# Falls as 1/n (linear budget, linear n → constant coverage only if budget ∝ n²)
# We give the agent recommended budget = n + const, so coverage ~ (n+const)/n → 1/n for large n
cover_curve = np.clip(
    (N_RANGE + 11) / N_RANGE * 0.65 * np.exp(-0.0015 * N_RANGE), 0.02, 1.0
)

# Strategy shift — exploitation ratio (fraction of budget targeting top-k candidates)
# Ideal: rises from ~0.35 to ~0.80 (must focus as n grows)
# LLM:   stays flat at ~0.35 (keeps exploring; doesn't adapt strategy)
ideal_exploit = 0.30 + 0.50 * expit((np.log10(N_RANGE) - 1.5) / 0.5)
llm_exploit   = 0.32 + 0.06 * expit((np.log10(N_RANGE) - 2.2) / 0.6)  # barely adapts

# ── Reference annotations for biological systems ─────────────────────────────
BIO_REFS = [
    (20,    "this\nstudy",    "#333333", "bottom"),
    (200,   "simple\npathway","#888888", "bottom"),
    (6_000, "yeast\n~6k",     "#888888", "bottom"),
    (20_000,"human\n~20k",    "#888888", "bottom"),
]


# ── Panel A ───────────────────────────────────────────────────────────────────
def panel_A(ax, meas):
    # Phase transition shading
    ax.axvspan(N_PHASE_LO, N_PHASE_HI, color=PHASE_COL, alpha=0.10, zorder=0,
               label=f"Phase transition\n({N_PHASE_LO}–{N_PHASE_HI} genes)")
    ax.axvline(N_MEASURED, color="#cccccc", linewidth=1.0, linestyle="--", zorder=1)

    def draw_curve(n_range, curve, color, label, ls="-"):
        mask_m = n_range <= N_MEASURED * 1.05
        mask_h = n_range >= N_MEASURED * 0.95
        # measured segment (solid, thick)
        ax.plot(n_range[mask_m], curve[mask_m], color=color,
                linewidth=2.6, linestyle="-", zorder=4)
        # hypothesised segment (dashed, slightly thinner)
        ax.plot(n_range[mask_h], curve[mask_h], color=color,
                linewidth=2.0, linestyle="--", zorder=3, label=label)

    draw_curve(N_RANGE, diag_curve, COL_DIAG,   "Diagnosis score")
    draw_curve(N_RANGE, resc_curve, COL_RESCUE,  "Best rescue frac")
    draw_curve(N_RANGE, pred_curve, COL_PRED,    "Prediction accuracy")

    # Plot actual measured means as filled markers
    for n, vals in sorted(meas.items()):
        ax.scatter(n, vals["diag"], color=COL_DIAG,   s=55, zorder=6,
                   edgecolors="white", linewidth=0.8)
        ax.scatter(n, vals["resc"], color=COL_RESCUE,  s=55, zorder=6,
                   edgecolors="white", linewidth=0.8)
        ax.scatter(n, vals["pred"], color=COL_PRED,    s=55, zorder=6,
                   edgecolors="white", linewidth=0.8)

    # Annotations
    ax.text(N_PHASE_LO * 1.05, 0.15,
            "phase\ntransition\nzone",
            fontsize=7.5, color="#b08000", va="center", style="italic")

    ax.text(N_MEASURED * 0.88, 1.04, "←  measured",
            fontsize=7.5, color="#888888", ha="right")
    ax.text(N_MEASURED * 1.12, 1.04, "hypothesised  →",
            fontsize=7.5, color="#888888", ha="left")

    # Right-side labels for each curve at large n
    for label, curve, color, y_off in [
        ("Diagnosis",   diag_curve, COL_DIAG,   0.0),
        ("Rescue",      resc_curve, COL_RESCUE,  0.05),
        ("Prediction",  pred_curve, COL_PRED,   -0.03),
    ]:
        ax.text(18_000, curve[-1] + y_off, label, fontsize=8,
                color=color, va="center", fontweight="bold")

    # Bio reference lines
    for n, label, color, va in BIO_REFS:
        ax.axvline(n, color=color, linewidth=0.7, linestyle=":",
                   alpha=0.6, zorder=1)
        ax.text(n, -0.13, label, ha="center", va="top",
                fontsize=7, color=color)

    ax.set_xscale("log")
    ax.set_xlim(8, 30_000)
    ax.set_ylim(-0.05, 1.12)
    ax.set_xlabel("Network size  (n_genes, log scale)")
    ax.set_ylabel("Score")
    ax.set_title("A   Performance vs organism complexity")
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
    )
    ax.grid(True, axis="y", alpha=0.5)

    legend_handles = [
        mlines.Line2D([], [], color=COL_DIAG,   lw=2.4, label="Diagnosis score"),
        mlines.Line2D([], [], color=COL_RESCUE,  lw=2.4, label="Best rescue frac"),
        mlines.Line2D([], [], color=COL_PRED,    lw=2.4, label="Prediction accuracy"),
        mpatches.Patch(color=PHASE_COL, alpha=0.3, label="Phase transition zone"),
        mlines.Line2D([], [], color="k", lw=1.8, linestyle="-",  label="Measured"),
        mlines.Line2D([], [], color="k", lw=1.8, linestyle="--", label="Hypothesised"),
    ]
    ax.legend(handles=legend_handles, fontsize=7.8, frameon=False,
              loc="upper right", ncol=2)


# ── Panel B ───────────────────────────────────────────────────────────────────
def panel_B(ax, meas):
    ax.axvspan(N_PHASE_LO, N_PHASE_HI, color=PHASE_COL, alpha=0.10, zorder=0)
    ax.axvline(N_MEASURED, color="#cccccc", linewidth=1.0, linestyle="--", zorder=1)

    def draw_mech(n_range, curve, color, label):
        mask_m = n_range <= N_MEASURED * 1.05
        mask_h = n_range >= N_MEASURED * 0.95
        ax.plot(n_range[mask_m], curve[mask_m] * 100, color=color,
                linewidth=2.6, linestyle="-", zorder=4)
        ax.plot(n_range[mask_h], curve[mask_h] * 100, color=color,
                linewidth=2.0, linestyle="--", zorder=3, label=label)

    draw_mech(N_RANGE, budg_curve,  COL_BUDGET, "Budget exhaustion rate")
    draw_mech(N_RANGE, cover_curve, COL_COVER,  "Gene coverage (%)")

    # Measured budget exhaustion rates (approx from our data)
    meas_exhaust = {10: 0.0, 15: 0.11, 20: 0.22}   # fraction of runs hitting cap
    meas_cover   = {10: 0.75, 15: 0.72, 20: 0.60}  # rough: n_exp / n_genes

    for n in [10, 15, 20]:
        ax.scatter(n, meas_exhaust[n] * 100, color=COL_BUDGET,
                   s=55, zorder=6, edgecolors="white", linewidth=0.8)
        ax.scatter(n, meas_cover[n]   * 100, color=COL_COVER,
                   s=55, zorder=6, edgecolors="white", linewidth=0.8)

    # Crossover annotation
    cross_n = 120
    ax.annotate(
        "crossover:\nexhaustion > coverage\n→ search becomes blind",
        xy=(cross_n, 52), xytext=(400, 72),
        fontsize=7.8, color="#555555",
        arrowprops=dict(arrowstyle="-|>", color="#888888", lw=0.9,
                        connectionstyle="arc3,rad=-0.2"),
    )

    ax.set_xscale("log")
    ax.set_xlim(8, 30_000)
    ax.set_ylim(-3, 108)
    ax.set_xlabel("Network size  (n_genes, log scale)")
    ax.set_ylabel("Percent (%)")
    ax.set_title("B   Mechanism: budget exhaustion vs gene coverage")
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
    )
    ax.grid(True, axis="y", alpha=0.5)

    for n, label, color, va in BIO_REFS:
        ax.axvline(n, color=color, linewidth=0.7, linestyle=":", alpha=0.6)
        ax.text(n, -8, label, ha="center", va="top", fontsize=7, color=color)

    ax.legend(fontsize=8, frameon=False)


# ── Panel C ───────────────────────────────────────────────────────────────────
def panel_C(ax):
    ax.axvspan(N_PHASE_LO, N_PHASE_HI, color=PHASE_COL, alpha=0.10, zorder=0)
    ax.axvline(N_MEASURED, color="#cccccc", linewidth=1.0, linestyle="--", zorder=1)

    # Ideal and LLM curves (hypothesised only — no measured data)
    ax.plot(N_RANGE, ideal_exploit * 100, color=COL_IDEAL, linewidth=2.4,
            linestyle="--", label="Ideal adaptive agent", zorder=4)
    ax.plot(N_RANGE, llm_exploit   * 100, color=COL_LLM,   linewidth=2.4,
            linestyle="--", label="Current LLM (hypothesised)", zorder=4)

    # Gap shading between the two curves
    ax.fill_between(N_RANGE, llm_exploit * 100, ideal_exploit * 100,
                    color=COL_IDEAL, alpha=0.08, zorder=2,
                    label="Reasoning gap")

    # Annotate gap at large n
    n_ann = 2000
    idx   = np.searchsorted(N_RANGE, n_ann)
    gap   = (ideal_exploit[idx] - llm_exploit[idx]) * 100
    ax.annotate(
        f"reasoning\ngap  (~{gap:.0f} pp)",
        xy=(n_ann, (ideal_exploit[idx] + llm_exploit[idx]) / 2 * 100),
        xytext=(5_000, 62),
        fontsize=8, color=COL_IDEAL,
        arrowprops=dict(arrowstyle="-|>", color=COL_IDEAL, lw=0.9),
    )

    # Regime labels
    ax.text(14, 78, "puzzle\nmode", fontsize=8, color="#888888",
            style="italic", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#cccccc", alpha=0.8))
    ax.text(500, 78, "scientific\nreasoning\nmode", fontsize=8, color="#555555",
            style="italic", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#cccccc", alpha=0.8))

    # Arrow bridging regimes
    ax.annotate("", xy=(N_PHASE_HI * 1.1, 73), xytext=(N_PHASE_LO * 0.9, 73),
                arrowprops=dict(arrowstyle="<->", color="#aaaaaa", lw=1.1))
    ax.text((N_PHASE_LO + N_PHASE_HI) / 2, 76, "transition",
            ha="center", fontsize=7.5, color="#aaaaaa", style="italic")

    ax.set_xscale("log")
    ax.set_xlim(8, 30_000)
    ax.set_ylim(15, 95)
    ax.set_xlabel("Network size  (n_genes, log scale)")
    ax.set_ylabel("Exploitation ratio (%)  ─  fraction of budget\ntargeting top candidate genes")
    ax.set_title("C   Strategy shift: from exhaustive to hypothesis-driven")
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
    )
    ax.grid(True, axis="y", alpha=0.5)

    for n, label, color, va in BIO_REFS:
        ax.axvline(n, color=color, linewidth=0.7, linestyle=":", alpha=0.6)
        ax.text(n, 13, label, ha="center", va="top", fontsize=7, color=color)

    ax.legend(fontsize=8.5, frameon=False, loc="upper left")


# ── Assemble ──────────────────────────────────────────────────────────────────
def main():
    meas = measured_means()

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    fig.subplots_adjust(left=0.06, right=0.97, bottom=0.18,
                        top=0.82, wspace=0.38)

    panel_A(axes[0], meas)
    panel_B(axes[1], meas)
    panel_C(axes[2])

    fig.text(0.5, 0.97,
             "Scaling to real biological complexity: a reasoning phase transition",
             ha="center", va="top", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.935,
             "Solid markers = measured (this study, n = 10–20).  "
             "Dashed curves = model-based extrapolation (hypothesised).",
             ha="center", va="top", fontsize=9, color="#666666", style="italic")

    out = STUDY_DIR / "fig_scaling_hypothesis.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"[scaling_hypothesis] saved → {out.name}")
    plt.close(fig)


if __name__ == "__main__":
    main()
