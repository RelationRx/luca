#!/usr/bin/env python3
"""Visualise harder_regimes heuristic sweep results.

Layout (2 rows × 3 cols):
  Row 0 — Arm A (large n): metric vs n_genes (75/100), medium vs hard, mean ± seed range
  Row 1 — Arm B (budget sensitivity): metric vs budget_mult (0.5/0.75), n=35 vs n=50 hard

Usage:
    python fig_heuristic.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

STUDY_DIR    = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results_heuristic.jsonl"

records = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]

# ── Style ────────────────────────────────────────────────────────────────────
BG       = "#0d0d1a"
PANEL_BG = "#111122"
DIFF_COLOR  = {"medium": "#3fb950", "hard": "#f85149"}
BUDGET_COLOR = {0.5: "#f97316", 0.75: "#a78bfa"}
N_COLOR      = {35: "#60a5fa", 50: "#f472b6"}
SEED_MARKER  = {0: "o", 1: "s", 2: "^"}

METRICS = [
    ("malfunction_score",       "Diagnosis score"),
    ("best_rescue_fraction",    "Best rescue fraction"),
    ("avg_prediction_accuracy", "Prediction accuracy"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_arm_a(n, diff, key):
    return [
        r[key] for r in records
        if r["arm"] == "A" and r["n_genes"] == n
        and r["difficulty"] == diff and r.get(key) is not None
    ]


def get_arm_b(n, mult, key):
    return [
        r[key] for r in records
        if r["arm"] == "B" and r["n_genes"] == n
        and abs(r["budget_multiplier"] - mult) < 0.01
        and r.get(key) is not None
    ]


def style_ax(ax, xticks, xlabels):
    ax.set_facecolor(PANEL_BG)
    ax.set_ylim(-0.06, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.tick_params(colors="white", labelsize=8)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, color="white", fontsize=8.5)
    ax.axhline(1.0, color="#ffffff15", linewidth=1, linestyle="--")
    ax.axhline(0.5, color="#ffffff10", linewidth=1, linestyle=":")
    for sp in ax.spines.values():
        sp.set_edgecolor("#333")


# ── Figure ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(17, 10), facecolor=BG)
fig.patch.set_facecolor(BG)
fig.text(
    0.5, 0.985,
    "Harder Regimes — Heuristic Systematic-Sweep Agent",
    ha="center", va="top", color="#FFC107", fontsize=13, fontweight="bold",
)
fig.text(
    0.5, 0.962,
    "Arm A: n=75/100 × medium/hard @ 1.0× budget  ·  "
    "Arm B: n=35/50 hard × budget 0.50×/0.75×  ·  3 seeds each",
    ha="center", va="top", color="#888", fontsize=9,
)
plt.subplots_adjust(left=0.07, right=0.97, top=0.91, bottom=0.09,
                    hspace=0.42, wspace=0.30)

N_A_LEVELS   = [75, 100]
DIFFS        = ["medium", "hard"]
N_B_LEVELS   = [35, 50]
MULT_LEVELS  = [0.5, 0.75]

for col, (key, title) in enumerate(METRICS):

    # ── Row 0: Arm A — n × difficulty ────────────────────────────────────────
    ax = axes[0, col]
    xs_pos = {75: 0, 100: 1}

    for diff in DIFFS:
        cc = DIFF_COLOR[diff]
        means, lows, highs, xs = [], [], [], []
        for n in N_A_LEVELS:
            vals = get_arm_a(n, diff, key)
            if not vals:
                continue
            xs.append(xs_pos[n])
            means.append(np.mean(vals))
            lows.append(np.min(vals))
            highs.append(np.max(vals))

        if xs:
            ax.plot(xs, means, color=cc, linewidth=2.2, marker="o",
                    markersize=7, label=diff, zorder=3)
            ax.fill_between(xs, lows, highs, color=cc, alpha=0.15, zorder=2)

        # Per-seed dots
        gap = 0.14
        sign = -1 if diff == "medium" else +1
        for n in N_A_LEVELS:
            vals = get_arm_a(n, diff, key)
            xc   = xs_pos[n] + sign * gap
            for si, v in enumerate(vals):
                rng = np.random.default_rng(hash((n, diff, si, key, "A")) % 2**31)
                ax.scatter(xc + rng.uniform(-0.04, 0.04), v,
                           color=cc, marker=SEED_MARKER.get(si, "o"),
                           s=55, edgecolors="white", linewidths=0.6,
                           alpha=0.85, zorder=4)

    style_ax(ax, list(xs_pos.values()), [f"n={n}" for n in N_A_LEVELS])
    ax.set_title(title, color="white", fontsize=11, fontweight="bold", pad=7)
    ax.set_xlabel("n_genes  (Arm A)", color="#888", fontsize=8.5)
    if col == 0:
        ax.set_ylabel("Score", color="#888", fontsize=9)
        diff_handles = [mpatches.Patch(color=DIFF_COLOR[d], label=d) for d in DIFFS]
        ax.legend(handles=diff_handles, fontsize=8, facecolor="#1a1a2e",
                  edgecolor="#333", labelcolor="white", framealpha=0.9,
                  loc="lower left")

    # Annotate GOF/LOF breakdown for diagnosis column
    if key == "malfunction_score":
        for n_idx, n in enumerate(N_A_LEVELS):
            for diff in DIFFS:
                vals_d = [r for r in records if r["arm"] == "A"
                          and r["n_genes"] == n and r["difficulty"] == diff]
                gof_ok  = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_HI"
                              and r["malfunction_score"] == 1.0)
                gof_tot = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_HI")
                lof_ok  = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_LO"
                              and r["malfunction_score"] == 1.0)
                lof_tot = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_LO")
                sign    = -1 if diff == "medium" else +1
                xpos    = xs_pos[n] + sign * 0.14
                label   = f"G:{gof_ok}/{gof_tot}\nL:{lof_ok}/{lof_tot}"
                ax.text(xpos, -0.04, label, ha="center", va="top",
                        color=DIFF_COLOR[diff], fontsize=6.5, alpha=0.8)

    # ── Row 1: Arm B — budget × n_genes (hard only) ───────────────────────────
    ax2 = axes[1, col]
    xs_pos_b = {0.5: 0, 0.75: 1}

    for n_b in N_B_LEVELS:
        cc = N_COLOR[n_b]
        means, lows, highs, xs = [], [], [], []
        for mult in MULT_LEVELS:
            vals = get_arm_b(n_b, mult, key)
            if not vals:
                continue
            xs.append(xs_pos_b[mult])
            means.append(np.mean(vals))
            lows.append(np.min(vals))
            highs.append(np.max(vals))

        if xs:
            ax2.plot(xs, means, color=cc, linewidth=2.2, marker="D",
                     markersize=7, label=f"n={n_b}", zorder=3)
            ax2.fill_between(xs, lows, highs, color=cc, alpha=0.15, zorder=2)

        # Per-seed dots
        gap  = 0.12
        sign = -1 if n_b == 35 else +1
        for mult in MULT_LEVELS:
            vals = get_arm_b(n_b, mult, key)
            xc   = xs_pos_b[mult] + sign * gap
            for si, v in enumerate(vals):
                rng = np.random.default_rng(hash((n_b, mult, si, key, "B")) % 2**31)
                ax2.scatter(xc + rng.uniform(-0.04, 0.04), v,
                            color=cc, marker=SEED_MARKER.get(si, "o"),
                            s=55, edgecolors="white", linewidths=0.6,
                            alpha=0.85, zorder=4)

        # Annotate GOF/LOF breakdown for diagnosis column
        if key == "malfunction_score":
            for mult in MULT_LEVELS:
                vals_d = [r for r in records if r["arm"] == "B"
                          and r["n_genes"] == n_b
                          and abs(r["budget_multiplier"] - mult) < 0.01]
                gof_ok  = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_HI"
                              and r["malfunction_score"] == 1.0)
                gof_tot = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_HI")
                lof_ok  = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_LO"
                              and r["malfunction_score"] == 1.0)
                lof_tot = sum(1 for r in vals_d if r["malfunction_type"] == "LOCK_LO")
                sign2   = -1 if n_b == 35 else +1
                xpos    = xs_pos_b[mult] + sign2 * 0.12
                label   = f"G:{gof_ok}/{gof_tot}\nL:{lof_ok}/{lof_tot}"
                ax2.text(xpos, -0.04, label, ha="center", va="top",
                         color=cc, fontsize=6.5, alpha=0.8)

    style_ax(ax2, list(xs_pos_b.values()), ["0.50×", "0.75×"])
    ax2.set_title(f"{title}  (hard, Arm B)", color="#aaa", fontsize=9.5, pad=7)
    ax2.set_xlabel("Budget multiplier", color="#888", fontsize=8.5)
    if col == 0:
        ax2.set_ylabel("Score", color="#888", fontsize=9)
        n_handles = [mpatches.Patch(color=N_COLOR[n], label=f"n={n}") for n in N_B_LEVELS]
        seed_handles = [
            plt.scatter([], [], c="white", marker=SEED_MARKER[s],
                        s=50, label=f"seed {s}", edgecolors="#888", linewidths=0.6)
            for s in [0, 1, 2]
        ]
        ax2.legend(handles=n_handles + seed_handles,
                   fontsize=7.5, facecolor="#1a1a2e", edgecolor="#333",
                   labelcolor="white", framealpha=0.9, loc="lower left")

# ── Footnote ─────────────────────────────────────────────────────────────────
fig.text(
    0.5, 0.005,
    "G:k/n = LOCK_HI correct/total · L:k/n = LOCK_LO correct/total · "
    "Heuristic: BLOCK-sweep all visible nodes, BOOST-sweep top-5 LOCK_LO candidates, "
    "additive prediction",
    ha="center", va="bottom", color="#555", fontsize=7.5,
)

out_path = STUDY_DIR / "fig_heuristic.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out_path}")
plt.close()
