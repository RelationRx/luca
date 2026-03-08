#!/usr/bin/env python3
"""Visualise medium vs hard sweep results.

Layout (2 rows):
  Row 1: Line plots — metric vs n_genes, medium vs hard, mean ± range across seeds
  Row 2: Per-seed dot strip plots — shows individual seed variance

Usage:
    python fig_results.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

STUDY_DIR    = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

N_GENES_LEVELS = [20, 35, 50]
DIFFICULTIES   = ["medium", "hard"]
SEEDS          = [0, 1, 2]

BG       = "#0d0d1a"
PANEL_BG = "#111122"

DIFF_COLOR  = {"medium": "#3fb950", "hard": "#f85149"}
DIFF_LABEL  = {"medium": "Medium  (no feedback↑, no latent)", "hard": "Hard  (feedback↑, 25% latent)"}
SEED_MARKER = {0: "o", 1: "s", 2: "^"}

METRICS = [
    ("malfunction_score",       "Diagnosis score"),
    ("best_rescue_fraction",    "Best rescue fraction"),
    ("avg_prediction_accuracy", "Prediction accuracy"),
]

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

records = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]


def get_vals(n, diff, key):
    return [
        r[key] for r in records
        if r["n_genes"] == n and r["difficulty"] == diff and r.get(key) is not None
    ]


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(2, 3, figsize=(18, 10), facecolor=BG)
fig.patch.set_facecolor(BG)
fig.text(
    0.5, 0.98,
    "Medium vs Hard — n_genes × difficulty  (3 seeds each, budget=1.0×)",
    ha="center", va="top", color="#FFC107", fontsize=13, fontweight="bold",
)

plt.subplots_adjust(left=0.07, right=0.97, top=0.91, bottom=0.09,
                    hspace=0.38, wspace=0.28)

jitter_x = 0.5   # horizontal jitter for strip plot

for col, (key, title) in enumerate(METRICS):

    # ── Row 0: line plot with mean ± range ───────────────────────────────────
    ax = axes[0, col]
    ax.set_facecolor(PANEL_BG)

    for diff in DIFFICULTIES:
        col_c = DIFF_COLOR[diff]
        means, lows, highs, xs = [], [], [], []
        for n in N_GENES_LEVELS:
            vals = get_vals(n, diff, key)
            if not vals:
                continue
            xs.append(n)
            means.append(np.mean(vals))
            lows.append(np.min(vals))
            highs.append(np.max(vals))

        if not xs:
            continue

        ax.plot(xs, means, color=col_c, linewidth=2.2, marker="o",
                markersize=7, label=DIFF_LABEL[diff], zorder=3)
        ax.fill_between(xs, lows, highs, color=col_c, alpha=0.15, zorder=2)

    ax.set_xticks(N_GENES_LEVELS)
    ax.set_xticklabels([f"n={n}" for n in N_GENES_LEVELS], color="white", fontsize=9)
    ax.set_ylim(-0.06, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.tick_params(colors="white")
    ax.axhline(1.0, color="#ffffff15", linewidth=1, linestyle="--")
    ax.axhline(0.5, color="#ffffff10", linewidth=1, linestyle=":")
    ax.set_title(title, color="white", fontsize=11, fontweight="bold", pad=7)
    ax.set_xlabel("n_genes", color="#888", fontsize=9)
    ax.set_ylabel("Score", color="#888", fontsize=9)
    for sp in ax.spines.values():
        sp.set_edgecolor("#333")
    if col == 0:
        ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333",
                  labelcolor="white", framealpha=0.9, loc="lower left")

    # ── Row 1: per-seed strip plot ────────────────────────────────────────────
    ax2 = axes[1, col]
    ax2.set_facecolor(PANEL_BG)

    x_positions = {n: i for i, n in enumerate(N_GENES_LEVELS)}
    gap = 0.22   # horizontal offset between medium and hard within same n

    for diff in DIFFICULTIES:
        col_c = DIFF_COLOR[diff]
        sign  = -1 if diff == "medium" else +1
        for n in N_GENES_LEVELS:
            vals = get_vals(n, diff, key)
            xc   = x_positions[n] + sign * gap
            for si, v in enumerate(vals):
                rng = np.random.default_rng(hash((n, diff, si, key)) % 2**31)
                jx  = rng.uniform(-0.05, 0.05)
                ax2.scatter(xc + jx, v, color=col_c,
                            marker=SEED_MARKER.get(si, "o"),
                            s=70, edgecolors="white", linewidths=0.7,
                            alpha=0.88, zorder=3)
            # Mean bar
            if vals:
                ax2.plot([xc - 0.1, xc + 0.1], [np.mean(vals)] * 2,
                         color=col_c, linewidth=2.2, zorder=4)

    ax2.set_xticks(list(x_positions.values()))
    ax2.set_xticklabels([f"n={n}" for n in N_GENES_LEVELS], color="white", fontsize=9)
    ax2.set_ylim(-0.06, 1.08)
    ax2.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax2.tick_params(colors="white")
    ax2.axhline(1.0, color="#ffffff15", linewidth=1, linestyle="--")
    ax2.axhline(0.5, color="#ffffff10", linewidth=1, linestyle=":")
    ax2.set_title(f"{title}  (per seed)", color="#aaa", fontsize=9.5, pad=7)
    ax2.set_xlabel("n_genes", color="#888", fontsize=9)
    for sp in ax2.spines.values():
        sp.set_edgecolor("#333")

    # Seed legend on last column only
    if col == 2:
        seed_handles = [
            plt.scatter([], [], c="white", marker=SEED_MARKER[s],
                        s=60, label=f"seed {s}", edgecolors="#888", linewidths=0.7)
            for s in SEEDS
        ]
        diff_handles = [
            mpatches.Patch(color=DIFF_COLOR[d], label=d) for d in DIFFICULTIES
        ]
        ax2.legend(handles=diff_handles + seed_handles,
                   fontsize=7.5, facecolor="#1a1a2e", edgecolor="#333",
                   labelcolor="white", framealpha=0.9, loc="lower left")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

out_path = STUDY_DIR / "fig_results.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out_path}")
plt.close()
