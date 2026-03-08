#!/usr/bin/env python3
"""
Mock figure: Two new research directions — provisional hypotheses.

  A  Knowledge-guided search efficiency
     How well does the agent's experiment selection track the true causal path?
     Measured (n≤20) vs hypothesized (n>20).

  B  Metacognitive test: solvable vs unsolvable organism detection
     Can the agent stop when the problem is underdetermined,
     or does it run to budget exhaustion?

All curves are provisional — subject to experimental validation.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np
from scipy.special import expit
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE   = "#2979ff"
TEAL   = "#00897b"
ORANGE = "#e65100"
RED    = "#c62828"
GREY   = "#78909c"
TXT    = "#0f172a"
SUB    = "#64748b"
PROV   = "#b0b8c4"   # provisional / hypothesized colour

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

MEAS_CUTOFF = 20   # n_genes ≤ this are measured; beyond is hypothesized


# ─── Panel A: Search efficiency ───────────────────────────────────────────────
def panel_A(ax):
    """
    X: n_genes (log scale)
    Y: causal search efficiency — fraction of experiments targeting genes
       causally proximal to the true malfunction.

    Ideal agent: flat (maintains relevance regardless of network size).
    Current LLM: high at small n, decays as network grows.
    Gap = the knowledge component we don't yet understand.
    """
    n_all = np.array([10, 15, 20, 35, 60, 100, 200, 400])
    n_meas = n_all[n_all <= MEAS_CUTOFF]
    n_hyp  = n_all[n_all >  MEAS_CUTOFF]

    # Ideal agent (knowledge-guided): nearly flat, slight improvement
    ideal_all  = 0.76 + 0.06 * expit((np.log(n_all) - np.log(80)) * 1.2)

    # Current LLM: decays via sigmoid on log scale
    agent_all  = 0.72 * (1 - expit((np.log(n_all) - np.log(35)) * 1.5)) + 0.07

    ideal_meas = ideal_all[:len(n_meas)]
    agent_meas = agent_all[:len(n_meas)]
    ideal_hyp  = ideal_all[len(n_meas):]
    agent_hyp  = agent_all[len(n_meas):]

    x_all = np.log10(n_all)
    x_meas = np.log10(n_meas)
    x_hyp  = np.log10(n_hyp)

    # ── Knowledge gap shading ──
    ax.fill_between(x_all, agent_all, ideal_all,
                    color=ORANGE, alpha=0.10, zorder=1, label="_nolegend_")
    ax.text(np.log10(80), 0.60,
            "knowledge\ngap", ha="center", va="center",
            fontsize=9.5, color=ORANGE, style="italic", alpha=0.75)

    # ── Ideal agent ──
    ax.plot(x_meas, ideal_meas, color=TEAL, lw=2.5,
            marker="o", markersize=7, zorder=4, label="Ideal (knowledge-guided)")
    ax.plot(x_hyp, ideal_hyp, color=TEAL, lw=2.0, linestyle="--",
            marker="o", markersize=6, markerfacecolor="white",
            markeredgewidth=1.8, zorder=3, label="_nolegend_")

    # ── Current LLM ──
    ax.plot(x_meas, agent_meas, color=BLUE, lw=2.5,
            marker="s", markersize=7, zorder=4, label="Current LLM agent")
    ax.plot(x_hyp, agent_hyp, color=BLUE, lw=2.0, linestyle="--",
            marker="s", markersize=6, markerfacecolor="white",
            markeredgewidth=1.8, zorder=3, label="_nolegend_")

    # ── Measured region band ──
    ax.axvspan(np.log10(8), np.log10(MEAS_CUTOFF + 2),
               color="#f0f9ff", alpha=0.6, zorder=0)
    ax.text(np.log10(14), 0.97, "measured",
            ha="center", va="top", fontsize=8.5, color=BLUE, style="italic")

    # ── Hypothesized region annotation ──
    ax.axvline(np.log10(MEAS_CUTOFF + 2), color=PROV, lw=1.2, linestyle=":",
               zorder=2)
    ax.text(np.log10(60), 0.97, "hypothesized ···",
            ha="center", va="top", fontsize=8.5, color=PROV, style="italic")

    # ── Phase transition annotation ──
    ax.annotate(
        "search becomes\nunguided",
        xy=(np.log10(55), agent_all[n_all == 60][0]),
        xytext=(np.log10(55) - 0.35, 0.25),
        fontsize=8.5, color=BLUE,
        arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.0),
    )

    ax.set_xlim(np.log10(8), np.log10(500))
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(np.log10([10, 20, 50, 100, 200, 400]))
    ax.set_xticklabels(["10", "20", "50", "100", "200", "400"])
    ax.set_xlabel("Network size  (n genes, log scale)")
    ax.set_ylabel("Search efficiency\n(causal relevance of experiments)")
    ax.set_title("A   Knowledge-guided causal search")
    ax.grid(True, axis="y")
    ax.legend(fontsize=9.5, frameon=False, loc="upper right")

    ax.text(0.97, 0.02, "provisional — subject to experimental validation",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8, color=PROV, style="italic")


# ─── Panel B: Metacognitive test ──────────────────────────────────────────────
def panel_B(ax_main, ax_bar):
    """
    Main plot: budget utilisation vs budget multiplier.
      Solvable organisms (our data): utilisation drops — agent stops when confident.
      Unsolvable organisms (hypothesised): utilisation stays near 1.0 — exhaustion.

    Inset bar: P(correct outcome) for each case.
    """
    bm = np.array([0.5, 1.0, 1.5, 2.0])

    # Budget utilisation (used / total)
    # Solvable: agent stops early — from existing data + extrapolate
    util_solv = np.array([0.94, 0.86, 0.68, 0.60])
    # Unsolvable: no stopping signal — runs to exhaustion
    util_unsolv = np.array([0.97, 0.99, 1.00, 1.00])

    meas_mask = bm <= 1.5  # 2.0× is hypothesized

    def plot_line(xs, ys, col, label, measured_mask, marker):
        xm, ym = xs[measured_mask], ys[measured_mask]
        xh, yh = xs[~measured_mask], ys[~measured_mask]
        ax_main.plot(xm, ym, color=col, lw=2.5, marker=marker,
                     markersize=8, zorder=4, label=label)
        ax_main.plot(xh, yh, color=col, lw=2.0, linestyle="--",
                     marker=marker, markersize=7,
                     markerfacecolor="white", markeredgewidth=1.8,
                     zorder=3)

    plot_line(bm, util_solv,  TEAL, "Solvable organism",   meas_mask, "o")
    plot_line(bm, util_unsolv, RED,  "Unsolvable organism", meas_mask, "^")

    # Shading between the curves
    ax_main.fill_between(bm, util_solv, util_unsolv,
                         color=RED, alpha=0.08, zorder=1)
    ax_main.text(1.5, 0.86,
                 "metacognitive\ngap",
                 ha="center", va="center",
                 fontsize=9.5, color=RED, style="italic", alpha=0.70)

    # Annotations
    ax_main.annotate(
        "agent stops\nwhen confident",
        xy=(1.5, util_solv[bm == 1.5][0]),
        xytext=(1.22, 0.55),
        fontsize=8.5, color=TEAL,
        arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=1.0),
    )
    ax_main.annotate(
        "budget exhaustion —\nno stopping signal",
        xy=(1.5, util_unsolv[bm == 1.5][0]),
        xytext=(1.18, 1.06),
        fontsize=8.5, color=RED,
        arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.0),
    )

    ax_main.axhline(1.0, color="#cbd5e1", lw=0.9, linestyle=":", zorder=0)
    ax_main.axvline(1.5 + 0.08, color=PROV, lw=1.1, linestyle=":",
                    zorder=2)
    ax_main.text(1.62, 0.62, "hyp.", fontsize=8, color=PROV, style="italic")

    ax_main.set_xlim(0.35, 2.15)
    ax_main.set_ylim(0.45, 1.15)
    ax_main.set_xticks([0.5, 1.0, 1.5, 2.0])
    ax_main.set_xticklabels(["0.5×\n(tight)", "1.0×\n(rec.)", "1.5×\n(generous)", "2.0×\n(excess)"])
    ax_main.set_xlabel("Budget multiplier")
    ax_main.set_ylabel("Budget utilisation  (used / total)")
    ax_main.set_title("B   Metacognitive test: solvable vs unsolvable")
    ax_main.grid(True, axis="y")
    ax_main.legend(fontsize=9.5, frameon=False, loc="lower left")

    ax_main.text(0.98, 0.02, "provisional",
                 transform=ax_main.transAxes, ha="right", va="bottom",
                 fontsize=8, color=PROV, style="italic")

    # ── Inset bar: P(correct outcome) ──────────────────────────────────────
    # Solvable: P(correct diagnosis)   Unsolvable: P(declares unsolvable)
    categories  = ["Solvable:\nP(correct)", "Unsolvable:\nP(declares\nunsolvable)"]
    heights     = [0.93, 0.10]   # 0.93 from our data; 0.10 hypothesized
    colours     = [TEAL, RED]
    hatch       = ["", "//"]     # hatched = fully hypothesized

    bars = ax_bar.bar(categories, heights, color=colours, alpha=0.75,
                      width=0.5, edgecolor=colours, linewidth=1.5,
                      hatch=hatch[0], zorder=3)
    bars[1].set_hatch("//")
    bars[1].set_alpha(0.45)

    for bar, h in zip(bars, heights):
        ax_bar.text(bar.get_x() + bar.get_width() / 2,
                    h + 0.03, f"{h:.0%}",
                    ha="center", va="bottom", fontsize=10,
                    fontweight="bold",
                    color=TEAL if h > 0.5 else RED)

    ax_bar.axhline(0.5, color="#cbd5e1", lw=0.9, linestyle=":", zorder=0)
    ax_bar.set_ylim(0, 1.15)
    ax_bar.set_ylabel("Probability")
    ax_bar.set_title("Outcome at 1.0×", fontsize=10)
    ax_bar.grid(True, axis="y")
    ax_bar.text(0.97, 0.02, "hatched = hypothesized",
                transform=ax_bar.transAxes, ha="right", va="bottom",
                fontsize=7.5, color=PROV, style="italic")


# ─── Assemble ─────────────────────────────────────────────────────────────────
def main():
    fig = plt.figure(figsize=(14, 5.8))
    gs = fig.add_gridspec(
        1, 3,
        width_ratios=[1.35, 1.2, 0.55],
        left=0.07, right=0.97,
        bottom=0.14, top=0.82,
        wspace=0.40,
    )

    ax_A    = fig.add_subplot(gs[0])
    ax_B    = fig.add_subplot(gs[1])
    ax_Bbar = fig.add_subplot(gs[2])

    panel_A(ax_A)
    panel_B(ax_B, ax_Bbar)

    fig.text(0.5, 0.98,
             "Beyond budget scaling: knowledge efficiency and metacognitive awareness",
             ha="center", va="top", fontsize=13, fontweight="bold", color=TXT)
    fig.text(0.5, 0.935,
             "Provisional hypotheses — conclusions subject to change after running experiments",
             ha="center", va="top", fontsize=9.5, color=PROV, style="italic")

    out = STUDY_DIR / "fig_new_directions.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"[new_directions] saved → {out.name}")
    plt.close(fig)


if __name__ == "__main__":
    main()
