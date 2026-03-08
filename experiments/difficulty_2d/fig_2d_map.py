#!/usr/bin/env python3
"""2D heatmap: n_genes × difficulty for diagnosis / rescue / prediction scores.

Usage:
    python fig_2d_map.py
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

N_GENES_LEVELS = [10, 15, 20, 35]
DIFFICULTIES   = ["easy", "medium", "hard"]

BG       = "#0d0d1a"
PANEL_BG = "#111122"

METRICS = [
    ("malfunction_score",       "Diagnosis score",       "diag"),
    ("best_rescue_fraction",    "Best rescue fraction",  "rescue"),
    ("avg_prediction_accuracy", "Prediction accuracy",   "pred"),
]

# ---------------------------------------------------------------------------
# Load results
# ---------------------------------------------------------------------------

records = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]

def get_val(n, diff, key):
    matches = [r for r in records if r["n_genes"] == n and r["difficulty"] == diff]
    if not matches:
        return None
    return matches[-1].get(key)   # latest run if duplicated

# ---------------------------------------------------------------------------
# Figure: 1 row of 3 heatmaps + 1 summary scatter
# ---------------------------------------------------------------------------

fig = plt.figure(figsize=(20, 9), facecolor=BG)
fig.text(
    0.5, 0.98,
    "LEMONOIDS 2D Map — n_genes × difficulty  (single seed, budget=1.0×)",
    ha="center", va="top", color="#FFC107", fontsize=13, fontweight="bold",
)

gs = fig.add_gridspec(
    1, 4,
    width_ratios=[1, 1, 1, 1.1],
    wspace=0.32,
    left=0.07, right=0.97,
    top=0.88, bottom=0.12,
)

DIFF_COLORS = {"easy": "#58a6ff", "medium": "#3fb950", "hard": "#f85149"}
CMAP = plt.cm.RdYlGn   # red=0, green=1

# ── Heatmaps ────────────────────────────────────────────────────────────────

axes_hm = [fig.add_subplot(gs[0, i]) for i in range(3)]

for ax, (key, title, short) in zip(axes_hm, METRICS):
    ax.set_facecolor(PANEL_BG)

    mat = np.full((len(N_GENES_LEVELS), len(DIFFICULTIES)), np.nan)
    for ri, n in enumerate(N_GENES_LEVELS):
        for ci, diff in enumerate(DIFFICULTIES):
            v = get_val(n, diff, key)
            if v is not None:
                mat[ri, ci] = v

    im = ax.imshow(
        mat, cmap=CMAP, vmin=0, vmax=1,
        aspect="auto",
        extent=[-0.5, len(DIFFICULTIES) - 0.5, len(N_GENES_LEVELS) - 0.5, -0.5],
    )

    # Cell annotations
    for ri in range(len(N_GENES_LEVELS)):
        for ci in range(len(DIFFICULTIES)):
            v = mat[ri, ci]
            if np.isnan(v):
                ax.text(ci, ri, "—", ha="center", va="center",
                        color="#555", fontsize=11)
            else:
                tc = "white" if v < 0.6 else "#111"
                ax.text(ci, ri, f"{v:.2f}", ha="center", va="center",
                        color=tc, fontsize=12, fontweight="bold")

    ax.set_xticks(range(len(DIFFICULTIES)))
    ax.set_xticklabels(DIFFICULTIES, fontsize=10, color="white")
    ax.set_yticks(range(len(N_GENES_LEVELS)))
    ax.set_yticklabels([f"n={n}" for n in N_GENES_LEVELS], fontsize=10, color="white")
    ax.tick_params(colors="white", length=0)
    for sp in ax.spines.values():
        sp.set_edgecolor("#333")

    ax.set_title(title, color="white", fontsize=11, pad=8, fontweight="bold")

    # Axis labels
    ax.set_xlabel("Difficulty →", color="#888", fontsize=9)
    ax.set_ylabel("Network size →", color="#888", fontsize=9)

    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.ax.tick_params(colors="#aaa", labelsize=7)
    cb.outline.set_edgecolor("#333")

# ── Summary scatter: diag vs pred, coloured by difficulty ───────────────────

ax_sc = fig.add_subplot(gs[0, 3])
ax_sc.set_facecolor(PANEL_BG)

markers_n = {10: "o", 15: "s", 20: "^", 35: "D"}
sizes_n   = {10: 80,  15: 110, 20: 140, 35: 180}

jitter = 0.015   # small jitter to separate overlapping points

for n in N_GENES_LEVELS:
    for diff in DIFFICULTIES:
        diag = get_val(n, diff, "malfunction_score")
        pred = get_val(n, diff, "avg_prediction_accuracy")
        if diag is None or pred is None:
            continue
        jx = np.random.default_rng(hash((n, diff)) % 2**31).uniform(-jitter, jitter)
        jy = np.random.default_rng(hash((n, diff, 1)) % 2**31).uniform(-jitter, jitter)
        ax_sc.scatter(
            diag + jx, pred + jy,
            c=DIFF_COLORS[diff],
            marker=markers_n[n],
            s=sizes_n[n],
            edgecolors="white", linewidths=0.8,
            alpha=0.88, zorder=3,
        )
        ax_sc.annotate(
            f"n={n}", (diag + jx, pred + jy),
            xytext=(5, 4), textcoords="offset points",
            fontsize=7, color="#aaa",
        )

ax_sc.axhline(0.5, color="#ffffff20", linewidth=1, linestyle="--")
ax_sc.axvline(0.5, color="#ffffff20", linewidth=1, linestyle="--")

# Quadrant labels
for (tx, ty, label, col) in [
    (0.18, 0.93, "good pred\nbad diag",  "#FFC107"),
    (0.78, 0.93, "both good",            "#3fb950"),
    (0.18, 0.08, "both bad",             "#f85149"),
    (0.78, 0.08, "good diag\nbad pred",  "#58a6ff"),
]:
    ax_sc.text(tx, ty, label, transform=ax_sc.transAxes,
               color=col, fontsize=7.5, ha="center", va="center",
               style="italic", alpha=0.6)

ax_sc.set_xlim(-0.08, 1.12)
ax_sc.set_ylim(-0.08, 1.12)
ax_sc.set_xlabel("Diagnosis score", color="#aaa", fontsize=10)
ax_sc.set_ylabel("Prediction accuracy", color="#aaa", fontsize=10)
ax_sc.set_title("Diag vs Pred", color="white", fontsize=11, pad=8, fontweight="bold")
ax_sc.tick_params(colors="white")
for sp in ax_sc.spines.values():
    sp.set_edgecolor("#333")

# Legend: difficulty colour + n_genes shape
diff_handles = [
    mpatches.Patch(color=DIFF_COLORS[d], label=d) for d in DIFFICULTIES
]
n_handles = [
    plt.scatter([], [], c="white", marker=markers_n[n], s=sizes_n[n],
                label=f"n={n}", edgecolors="#888", linewidths=0.8)
    for n in N_GENES_LEVELS
]
ax_sc.legend(
    handles=diff_handles + n_handles,
    loc="lower left", fontsize=7.5,
    facecolor="#1a1a2e", edgecolor="#333", labelcolor="white", framealpha=0.9,
)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

out_path = STUDY_DIR / "fig_2d_map.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out_path}")
plt.close()
