#!/usr/bin/env python3
"""EDA for scaling_study_v1: plots + printed summary.

Generates:
  fig1_heatmaps.png     — 3×3 metric heatmaps (n_genes × budget_mult)
  fig2_trends.png       — line plots: metrics vs budget, per n_genes
  fig3_budget.png       — budget usage and experiment counts
  fig4_scatter.png      — per-run scatter: experiments used vs pred MSE,
                          coloured by diag_score
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
STUDY_DIR = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

N_GENES  = [10, 15, 20]
BUDGETS  = [0.5, 1.0, 1.5]
SEEDS    = [0, 1, 2]

DARK_BG   = "#0d1117"
PANEL_BG  = "#161b22"
GRID_C    = "#21262d"
TEXT_C    = "#e6edf3"
ACCENT    = "#58a6ff"
GREEN     = "#3fb950"
YELLOW    = "#d29922"
RED       = "#f85149"

CMAP_DIAG = "YlGn"
CMAP_MSE  = "YlOrRd_r"

plt.rcParams.update({
    "figure.facecolor":  DARK_BG,
    "axes.facecolor":    PANEL_BG,
    "axes.edgecolor":    GRID_C,
    "axes.labelcolor":   TEXT_C,
    "xtick.color":       TEXT_C,
    "ytick.color":       TEXT_C,
    "text.color":        TEXT_C,
    "grid.color":        GRID_C,
    "grid.linewidth":    0.6,
    "font.family":       "monospace",
    "font.size":         10,
    "axes.titlesize":    11,
    "figure.titlesize":  13,
})

# ---------------------------------------------------------------------------

def load() -> list[dict]:
    return [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]


def cell(records: list[dict], n: int, m: float) -> list[dict]:
    return [r for r in records if r["n_genes"] == n and abs(r["budget_multiplier"] - m) < 1e-9]


def mean_or_nan(vals: list) -> float:
    v = [x for x in vals if x is not None]
    return statistics.mean(v) if v else float("nan")


def std_or_nan(vals: list) -> float:
    v = [x for x in vals if x is not None]
    return statistics.stdev(v) if len(v) > 1 else 0.0


# ---------------------------------------------------------------------------
# Fig 1: Heatmaps
# ---------------------------------------------------------------------------

def fig_heatmaps(records: list[dict]) -> None:
    metrics = [
        ("malfunction_score",     "Diagnosis score",    CMAP_DIAG,  0, 1),
        ("best_rescue_fraction",  "Best rescue frac",   CMAP_DIAG,  0, 1),
        ("avg_prediction_accuracy","Prediction accuracy",CMAP_DIAG, 0, 1),
        ("avg_prediction_mse",    "Prediction MSE",     CMAP_MSE,   0, 0.025),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    fig.suptitle("Scaling Study — Mean metrics across 3 seeds", fontweight="bold", y=1.01)

    for ax, (key, title, cmap, vmin, vmax) in zip(axes, metrics):
        mat = np.full((len(N_GENES), len(BUDGETS)), np.nan)
        for i, n in enumerate(N_GENES):
            for j, m in enumerate(BUDGETS):
                vals = [r[key] for r in cell(records, n, m)]
                mat[i, j] = mean_or_nan(vals)

        im = ax.imshow(mat, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")

        ax.set_xticks(range(len(BUDGETS)))
        ax.set_xticklabels([f"{m:.1f}×" for m in BUDGETS])
        ax.set_yticks(range(len(N_GENES)))
        ax.set_yticklabels([f"n={n}" for n in N_GENES])
        ax.set_xlabel("Budget mult")
        ax.set_title(title)

        for i in range(len(N_GENES)):
            for j in range(len(BUDGETS)):
                val = mat[i, j]
                if not np.isnan(val):
                    txt = f"{val:.3f}" if key == "avg_prediction_mse" else f"{val:.2f}"
                    color = "black" if val > (vmax * 0.6) else TEXT_C
                    ax.text(j, i, txt, ha="center", va="center",
                            fontsize=9, color=color, fontweight="bold")

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(labelsize=8, colors=TEXT_C)
        cbar.outline.set_edgecolor(GRID_C)

    fig.tight_layout()
    out = STUDY_DIR / "fig1_heatmaps.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"[eda] saved {out.name}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 2: Trends (line + seed dots)
# ---------------------------------------------------------------------------

def fig_trends(records: list[dict]) -> None:
    metrics = [
        ("malfunction_score",      "Diagnosis score",     (0.0, 1.05), GREEN),
        ("best_rescue_fraction",   "Best rescue frac",    (0.0, 1.05), ACCENT),
        ("avg_prediction_accuracy","Prediction accuracy", (0.0, 1.05), YELLOW),
        ("avg_prediction_mse",     "Prediction MSE",      (0, None),   RED),
    ]

    colors_n = {10: "#58a6ff", 15: "#3fb950", 20: "#d29922", 35: "#f85149"}
    markers   = {10: "o", 15: "s", 20: "^", 35: "D"}

    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5), sharey=False)
    fig.suptitle("Metric trends vs budget multiplier (mean ± 1 seed std)", fontweight="bold", y=1.01)

    for ax, (key, title, ylim, _) in zip(axes, metrics):
        for n in N_GENES:
            means, stds, xs = [], [], []
            for m in BUDGETS:
                vals = [r[key] for r in cell(records, n, m)]
                means.append(mean_or_nan(vals))
                stds.append(std_or_nan(vals))
                xs.append(m)

            c = colors_n[n]
            mk = markers[n]
            means_arr = np.array(means, dtype=float)
            stds_arr  = np.array(stds, dtype=float)

            ax.plot(xs, means_arr, color=c, marker=mk, linewidth=2,
                    markersize=8, label=f"n={n}", zorder=3)
            ax.fill_between(xs,
                            means_arr - stds_arr,
                            means_arr + stds_arr,
                            color=c, alpha=0.15)

            # Individual seed dots (jittered slightly)
            jitter = {10: -0.03, 15: 0.0, 20: 0.03}[n]
            for m in BUDGETS:
                vals = [r[key] for r in cell(records, n, m) if r[key] is not None]
                ax.scatter([m + jitter] * len(vals), vals,
                           color=c, s=18, alpha=0.55, zorder=4)

        ax.set_xticks(BUDGETS)
        ax.set_xticklabels([f"{m:.1f}×" for m in BUDGETS])
        ax.set_xlabel("Budget multiplier")
        ax.set_title(title)
        ax.set_ylim(ylim)
        ax.grid(True, axis="y")
        ax.legend(fontsize=8)

    fig.tight_layout()
    out = STUDY_DIR / "fig2_trends.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"[eda] saved {out.name}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 3: Budget usage
# ---------------------------------------------------------------------------

def fig_budget(records: list[dict]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    fig.suptitle("Budget usage & experiment counts", fontweight="bold", y=1.01)

    # 3a: Budget efficiency heatmap (used/total)
    ax = axes[0]
    mat = np.full((len(N_GENES), len(BUDGETS)), np.nan)
    for i, n in enumerate(N_GENES):
        for j, m in enumerate(BUDGETS):
            vals = [r["budget_used"] / r["budget_total"] for r in cell(records, n, m)
                    if r["budget_total"]]
            mat[i, j] = mean_or_nan(vals)
    im = ax.imshow(mat, cmap="Blues", vmin=0.3, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(BUDGETS)))
    ax.set_xticklabels([f"{m:.1f}×" for m in BUDGETS])
    ax.set_yticks(range(len(N_GENES)))
    ax.set_yticklabels([f"n={n}" for n in N_GENES])
    ax.set_xlabel("Budget mult")
    ax.set_title("Mean budget efficiency\n(used / total)")
    for i in range(len(N_GENES)):
        for j in range(len(BUDGETS)):
            v = mat[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0%}", ha="center", va="center",
                        fontsize=10, fontweight="bold",
                        color="black" if v > 0.65 else TEXT_C)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8, colors=TEXT_C)
    cbar.outline.set_edgecolor(GRID_C)

    # 3b: Budget used vs budget total scatter (all 27 runs)
    ax = axes[1]
    colors_n = {10: "#58a6ff", 15: "#3fb950", 20: "#d29922"}
    for n in N_GENES:
        subset = [r for r in records if r["n_genes"] == n]
        xs = [r["budget_total"] for r in subset]
        ys = [r["budget_used"] for r in subset]
        ax.scatter(xs, ys, color=colors_n[n], s=60, label=f"n={n}",
                   edgecolors="white", linewidth=0.5, zorder=3)
    lim = max(r["budget_total"] for r in records) + 5
    ax.plot([0, lim], [0, lim], "--", color=GRID_C, linewidth=1, label="100% used")
    ax.set_xlabel("Budget total")
    ax.set_ylabel("Budget used")
    ax.set_title("Budget used vs allocated\n(all 27 runs)")
    ax.legend(fontsize=8)
    ax.grid(True)

    # 3c: n_experiments vs budget_total, coloured by n_genes
    ax = axes[2]
    for n in N_GENES:
        subset = [r for r in records if r["n_genes"] == n]
        xs = [r["budget_total"] for r in subset]
        ys = [r["n_experiments"] for r in subset]
        ax.scatter(xs, ys, color=colors_n[n], s=60, label=f"n={n}",
                   edgecolors="white", linewidth=0.5, zorder=3)
    ax.set_xlabel("Budget total")
    ax.set_ylabel("# experiments run")
    ax.set_title("Experiments run vs budget\n(all 27 runs)")
    ax.legend(fontsize=8)
    ax.grid(True)

    fig.tight_layout()
    out = STUDY_DIR / "fig3_budget.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"[eda] saved {out.name}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 4: Per-run scatter — diagnosis coloured
# ---------------------------------------------------------------------------

def fig_scatter(records: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Per-run detail (coloured by diagnosis score)", fontweight="bold", y=1.01)

    score_color = {1.0: GREEN, 0.5: YELLOW, 0.0: RED}
    budget_labels = {0.5: "▲ 0.5×", 1.0: "● 1.0×", 1.5: "■ 1.5×"}
    markers_b = {0.5: "^", 1.0: "o", 1.5: "s"}

    # 4a: n_experiments vs pred_accuracy, shape=budget_mult, colour=diag_score
    ax = axes[0]
    for r in records:
        sc = r["malfunction_score"]
        bm = r["budget_multiplier"]
        pa = r["avg_prediction_accuracy"]
        ne = r["n_experiments"]
        if pa is None:
            pa = -0.05   # plot below axis to mark missing
        ax.scatter(ne, pa, color=score_color.get(sc, "gray"),
                   marker=markers_b[bm], s=80,
                   edgecolors="white", linewidth=0.4, zorder=3)
    ax.axhline(0, color=GRID_C, linewidth=0.8)
    ax.set_xlabel("# experiments run")
    ax.set_ylabel("Avg prediction accuracy")
    ax.set_title("Experiments vs prediction accuracy")
    ax.grid(True)
    # legend patches
    from matplotlib.lines import Line2D
    leg_score = [Line2D([0],[0], marker="o", color="w", markerfacecolor=c,
                        markersize=9, label=f"diag={s}")
                 for s, c in score_color.items()]
    leg_budget = [Line2D([0],[0], marker=mk, color=TEXT_C, linestyle="none",
                         markersize=8, label=budget_labels[bm])
                  for bm, mk in markers_b.items()]
    ax.legend(handles=leg_score + leg_budget, fontsize=8, ncol=2)

    # 4b: budget_used vs pred_mse, grouped by n_genes
    ax = axes[1]
    colors_n = {10: "#58a6ff", 15: "#3fb950", 20: "#d29922", 35: "#f85149"}
    for r in records:
        n = r["n_genes"]
        bu = r["budget_used"]
        pm = r["avg_prediction_mse"]
        sc = r["malfunction_score"]
        bm = r["budget_multiplier"]
        if pm is None:
            pm = 0.03   # sentinel for missing
        ax.scatter(bu, pm, color=colors_n[n],
                   marker=markers_b[bm], s=80,
                   edgecolors=score_color.get(sc, "gray"),
                   linewidth=1.8, zorder=3)
    ax.set_xlabel("Budget used")
    ax.set_ylabel("Avg prediction MSE")
    ax.set_title("Budget used vs prediction MSE\n(edge colour = diag score)")
    ax.grid(True)
    leg_n = [Line2D([0],[0], marker="o", color="w", markerfacecolor=c,
                    markersize=9, label=f"n={n}")
             for n, c in colors_n.items()]
    ax.legend(handles=leg_n, fontsize=8)

    fig.tight_layout()
    out = STUDY_DIR / "fig4_scatter.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"[eda] saved {out.name}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Printed summary
# ---------------------------------------------------------------------------

def print_summary(records: list[dict]) -> None:
    print()
    print("=" * 70)
    print("  SCALING STUDY v1 — EDA SUMMARY")
    print("=" * 70)

    total = len(records)
    diag_scores = [r["malfunction_score"] for r in records if r["malfunction_score"] is not None]
    rescue_fracs = [r["best_rescue_fraction"] for r in records if r["best_rescue_fraction"] is not None]
    pred_accs   = [r["avg_prediction_accuracy"] for r in records if r["avg_prediction_accuracy"] is not None]

    print(f"\n  Runs: {total}  |  Unique organisms: {len(set((r['n_genes'],r['seed']) for r in records))}")
    print(f"  Malfunction types: {sorted(set(r['malfunction_type'] for r in records))}")

    print(f"\n  Diagnosis score:     mean={statistics.mean(diag_scores):.3f}  "
          f"std={statistics.stdev(diag_scores):.3f}  "
          f"perfect={sum(s==1.0 for s in diag_scores)}/{len(diag_scores)}")
    print(f"  Best rescue frac:    mean={statistics.mean(rescue_fracs):.3f}  "
          f"std={statistics.stdev(rescue_fracs):.3f}  "
          f"perfect={sum(s==1.0 for s in rescue_fracs)}/{len(rescue_fracs)}")
    print(f"  Pred accuracy:       mean={statistics.mean(pred_accs):.3f}  "
          f"std={statistics.stdev(pred_accs):.3f}  "
          f"perfect={sum(s==1.0 for s in pred_accs)}/{len(pred_accs)}")

    print("\n  Budget efficiency (used/total):")
    for n in N_GENES:
        for m in BUDGETS:
            c = cell(records, n, m)
            effs = [r["budget_used"]/r["budget_total"] for r in c if r["budget_total"]]
            budgets = [r["budget_total"] for r in c]
            used    = [r["budget_used"] for r in c]
            print(f"    n={n}  {m:.1f}×  budget={budgets}  used={used}  "
                  f"eff={mean_or_nan(effs):.0%}")

    # Outlier / failure analysis
    failures = [r for r in records if (r["malfunction_score"] or 0) < 1.0]
    print(f"\n  Runs with diag_score < 1.0 ({len(failures)}):")
    for r in failures:
        sc = r["malfunction_score"]
        print(f"    n={r['n_genes']}  seed={r['seed']}  {r['budget_multiplier']:.1f}×  "
              f"diag={sc}  type={r['malfunction_type']}  target={r['malfunction_target']}  "
              f"budget_used={r['budget_used']}/{r['budget_total']}")

    # Budget effect on prediction
    print("\n  Prediction accuracy by budget multiplier (across all n_genes):")
    for m in BUDGETS:
        vals = [r["avg_prediction_accuracy"] for r in records
                if abs(r["budget_multiplier"] - m) < 1e-9
                and r["avg_prediction_accuracy"] is not None]
        print(f"    {m:.1f}×  mean={mean_or_nan(vals):.3f}  "
              f"std={std_or_nan(vals):.3f}  n={len(vals)}")

    print()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    records = load()
    print(f"[eda] Loaded {len(records)} records")
    print_summary(records)
    fig_heatmaps(records)
    fig_trends(records)
    fig_budget(records)
    fig_scatter(records)
    print("[eda] Done.")
