#!/usr/bin/env python3
"""
Compact eye-candy methods figure for LEMONOIDS.

Three-panel layout — large fonts, minimal text, visual-first:
  A  Generation pipeline  (left)
  B  Organism GRN anatomy  (centre, dominant)
  C  Disease model: malfunction cards + guarantee  (right)
"""
from __future__ import annotations
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from lemonoids.generation import generate_organism

# ── Palette ──────────────────────────────────────────────────────────────────
M0, M1, M2, M3 = "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"
MOD_COLS = [M0, M1, M2, M3]
ACT = "#16a34a"   # activating edge
INH = "#dc2626"   # inhibiting edge
SIG = "#f59e0b"   # signal node

GOF = "#dc2626"; LOF = "#6b7280"; CHR = "#d97706"; RSC = "#16a34a"
TXT = "#0f172a";  SUB = "#64748b"

plt.rcParams.update({
    "figure.facecolor": "white",
    "text.color": TXT,
    "font.family": "sans-serif",
    "font.size": 11,
})

SEED   = 42
KWARGS = dict(n_genes=10, n_modules=4, n_signals=3, n_phenotypes=3, seed=SEED)


def hex_to_rgba(h, alpha=0.10):
    r = int(h[1:3], 16) / 255
    g = int(h[3:5], 16) / 255
    b = int(h[5:7], 16) / 255
    return (r, g, b, alpha)


def rbox(ax, cx, cy, w, h, title, subtitle=None,
         fc="white", ec="#94a3b8", tfs=11, sfs=9, tcol=TXT, bold=True):
    ax.add_patch(mpatches.FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.05",
        facecolor=fc, edgecolor=ec, linewidth=1.8, zorder=3,
    ))
    ty = cy + (h * 0.14 if subtitle else 0)
    ax.text(cx, ty, title, ha="center", va="center",
            fontsize=tfs, fontweight="bold" if bold else "normal",
            color=tcol, zorder=4)
    if subtitle:
        ax.text(cx, cy - h * 0.22, subtitle, ha="center", va="center",
                fontsize=sfs, color=SUB, style="italic", zorder=4)


def varrow(ax, x, y1, y2, col="#94a3b8", lw=1.8):
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="-|>", color=col,
                                lw=lw, mutation_scale=13))


# ─── Panel A — Generation pipeline ───────────────────────────────────────────
def panel_A(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # Title
    ax.text(0.06, 0.99, "A", fontsize=16, fontweight="bold", va="top", color=TXT)
    ax.text(0.20, 0.99, "Generation pipeline",
            fontsize=13, fontweight="bold", va="top", color=TXT)

    CX = 0.46; W = 0.74; H = 0.10
    steps = [
        (0.84, "Genes + Modules",    "n genes planted into K modules",           M0),
        (0.67, "Regulatory Network", "signed GRN  (p_intra >> p_inter)",         M1),
        (0.50, "Signal Inputs",      "external activating / inhibiting inputs",  M2),
        (0.33, "Simulate Dynamics",  "x(t+1) = σ( b + Wx + s + ε )",            "#94a3b8"),
        (0.14, "Phenotype Readouts", "3 emergent readouts  P = σ(Σwx + b)",      M3),
    ]

    for cy, title, sub, ec in steps:
        rbox(ax, CX, cy, W, H, title, sub,
             fc=hex_to_rgba(ec if ec.startswith("#") and len(ec) == 7 else "#94a3b8"),
             ec=ec, tfs=11, sfs=8.5)

    for i in range(len(steps) - 1):
        varrow(ax, CX, steps[i][0] - H/2 - 0.005, steps[i+1][0] + H/2 + 0.005)

    # Disease branch off "Simulate Dynamics"
    sim_y = 0.33
    ax.annotate(
        "inject malfunction\n→ disease organism",
        xy=(CX + W/2 + 0.01, sim_y),
        xytext=(0.96, sim_y + 0.16),
        fontsize=8.5, fontweight="bold", color=GOF,
        ha="right", va="center",
        bbox=dict(boxstyle="round,pad=0.30", fc="#fee2e2", ec=GOF, lw=1.5),
        arrowprops=dict(arrowstyle="-|>", color=GOF, lw=1.3,
                        mutation_scale=10, connectionstyle="arc3,rad=-0.35"),
    )


# ─── Panel B — Organism anatomy (GRN) ────────────────────────────────────────
def panel_B(ax, org):
    import networkx as nx

    ax.axis("off")
    ax.text(0.05, 0.98, "B", fontsize=16, fontweight="bold", va="top",
            color=TXT, transform=ax.transAxes)
    ax.text(0.17, 0.98, "Organism anatomy",
            fontsize=13, fontweight="bold", va="top", color=TXT,
            transform=ax.transAxes)
    ax.text(0.17, 0.91,
            f"n={KWARGS['n_genes']} genes · {KWARGS['n_modules']} modules · "
            f"{KWARGS['n_signals']} signals  (seed={SEED})",
            fontsize=9.5, va="top", color=SUB, style="italic",
            transform=ax.transAxes)

    g2m = {}
    for k, mod in enumerate(org.modules):
        for gid in mod.gene_ids:
            g2m[gid] = k

    G = nx.DiGraph()
    for g in org.genes:
        G.add_node(g.id)
    for r in org.relations:
        G.add_edge(r.src, r.dst, etype=r.type)

    pos = nx.spring_layout(G, seed=SEED, k=2.8)

    # Module blobs
    for k, mod in enumerate(org.modules):
        pts = np.array([pos[gid] for gid in mod.gene_ids if gid in pos])
        if not len(pts):
            continue
        cx_, cy_ = pts.mean(0)
        rx = max(np.abs(pts[:, 0] - cx_).max(), 0.10) + 0.24
        ry = max(np.abs(pts[:, 1] - cy_).max(), 0.10) + 0.24
        ax.add_patch(mpatches.Ellipse(
            (cx_, cy_), rx * 2, ry * 2,
            facecolor=MOD_COLS[k], alpha=0.13,
            edgecolor=MOD_COLS[k], linewidth=2.2, linestyle="--", zorder=0,
        ))
        ax.text(cx_, cy_ + ry * 0.96, mod.label,
                fontsize=9.5, ha="center", va="bottom",
                color=MOD_COLS[k], style="italic", fontweight="bold",
                alpha=0.9, zorder=1)

    act_e = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "activates"]
    inh_e = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "inhibits"]
    kw = dict(arrows=True, arrowsize=18,
              connectionstyle="arc3,rad=0.12",
              min_source_margin=14, min_target_margin=14)
    nx.draw_networkx_edges(G, pos, ax=ax, edgelist=act_e,
                           edge_color=ACT, width=2.0, alpha=0.65, **kw)
    nx.draw_networkx_edges(G, pos, ax=ax, edgelist=inh_e,
                           edge_color=INH, width=2.0, alpha=0.65,
                           style="dashed", **kw)

    nc = [MOD_COLS[g2m.get(g.id, 0)] for g in org.genes]
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=nc,
                           node_size=900, linewidths=2.2, edgecolors="white")
    nx.draw_networkx_labels(G, pos, ax=ax,
                            labels={g.id: g.name for g in org.genes},
                            font_size=9, font_color="white", font_weight="bold")

    # Signals as diamonds
    all_pts = np.array(list(pos.values()))
    cen = all_pts.mean(0)
    for sig in org.signals:
        if not sig.targets or sig.targets[0] not in pos:
            continue
        tp = np.array(pos[sig.targets[0]])
        d = tp - cen; nd = np.linalg.norm(d)
        sp = tp + (d / nd) * 0.52 if nd > 0 else tp + 0.4
        ax.scatter(*sp, s=450, marker="D", color=SIG,
                   edgecolors="white", linewidths=1.5, zorder=5)
        ax.text(sp[0], sp[1] + 0.11, sig.label,
                fontsize=9.5, ha="center", va="bottom",
                color=SIG, fontweight="bold", zorder=6)
        ec_ = ACT if sig.mode == "activates" else INH
        for tgt in sig.targets[:2]:
            if tgt in pos:
                ax.annotate("", xy=pos[tgt], xytext=sp,
                            arrowprops=dict(arrowstyle="->", color=ec_,
                                            lw=1.5, alpha=0.50,
                                            connectionstyle="arc3,rad=0.1"))

    ax.set_aspect("equal")

    ax.legend(handles=[
        mlines.Line2D([], [], color=ACT, linewidth=2.2, label="activates"),
        mlines.Line2D([], [], color=INH, linewidth=2.2, linestyle="--", label="inhibits"),
        mlines.Line2D([], [], marker="D", color="w", markerfacecolor=SIG,
                      markersize=11, label="signal"),
    ], loc="lower left", fontsize=10.5, frameon=True,
       framealpha=0.90, edgecolor="#cbd5e1", borderpad=0.7)


# ─── Panel C — Disease model ──────────────────────────────────────────────────
def panel_C(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    ax.text(0.06, 0.99, "C", fontsize=16, fontweight="bold", va="top", color=TXT)
    ax.text(0.20, 0.99, "Disease model",
            fontsize=13, fontweight="bold", va="top", color=TXT)

    CARD_W = 0.28; CARD_H = 0.55
    CARD_TOP = 0.88   # top y of cards

    cards = [
        (0.18, "LOCK_HI", "Node locked high", "node saturated\n(bias → +∞)", "BLOCK rescues",  GOF, "#fee2e2"),
        (0.50, "LOCK_LO", "Node locked low",  "node silenced\n(bias → −∞)", "BOOST rescues",  LOF, "#f1f5f9"),
        (0.82, "PERSIST", "Persistent signal", "always active\n(strength ×10)", "deactivate rescues", CHR, "#fef3c7"),
    ]

    for cx, lbl, full, detail, rescue, col, bg in cards:
        cy_card = CARD_TOP - CARD_H / 2
        # outer card
        ax.add_patch(mpatches.FancyBboxPatch(
            (cx - CARD_W/2, cy_card - CARD_H/2), CARD_W, CARD_H,
            boxstyle="round,pad=0.04",
            facecolor=bg, edgecolor=col, linewidth=2.2, zorder=3,
        ))
        # divider between content and rescue section
        div_y = cy_card - CARD_H/2 + 0.12
        ax.plot([cx - CARD_W/2 + 0.02, cx + CARD_W/2 - 0.02],
                [div_y, div_y], color=col, lw=1.0, alpha=0.35, zorder=4)

        # top: type label (large) + full name + detail
        ax.text(cx, CARD_TOP - 0.05, lbl,
                ha="center", va="top",
                fontsize=17, fontweight="bold", color=col, zorder=4)
        ax.text(cx, CARD_TOP - 0.17, full,
                ha="center", va="top",
                fontsize=9.5, fontweight="bold", color=col, zorder=4)
        ax.text(cx, CARD_TOP - 0.27, detail,
                ha="center", va="top",
                fontsize=9, color=SUB, zorder=4, multialignment="center")

        # bottom: rescue label
        ax.text(cx, div_y + 0.07, "rescue:",
                ha="center", va="center",
                fontsize=8.5, color=SUB, style="italic", zorder=4)
        ax.text(cx, div_y + 0.025, rescue,
                ha="center", va="center",
                fontsize=10, fontweight="bold", color=RSC, zorder=4)

    # ── Detectability guarantee ──────────────────────────────────────────────
    gb_y = CARD_TOP - CARD_H - 0.09
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.04, gb_y - 0.14), 0.92, 0.19,
        boxstyle="round,pad=0.04",
        facecolor="#f0fdf4", edgecolor="#16a34a", linewidth=2.2, zorder=3,
    ))
    ax.text(0.50, gb_y + 0.01,
            "Detectability guarantee",
            ha="center", va="center",
            fontsize=12, fontweight="bold", color="#14532d", zorder=4)
    ax.text(0.50, gb_y - 0.03,
            "✓  ≥1 phenotype outside healthy corridor",
            ha="center", va="center",
            fontsize=10, color="#166534", zorder=4)
    ax.text(0.50, gb_y - 0.08,
            "✓  single targeted intervention restores health",
            ha="center", va="center",
            fontsize=10, color="#166534", zorder=4)


# ─── Assemble ─────────────────────────────────────────────────────────────────
def main():
    org = generate_organism(**KWARGS)

    fig = plt.figure(figsize=(17, 8))
    gs = fig.add_gridspec(
        1, 3,
        width_ratios=[0.78, 1.32, 0.90],
        left=0.03, right=0.98,
        bottom=0.03, top=0.90,
        wspace=0.07,
    )
    ax_A = fig.add_subplot(gs[0])
    ax_B = fig.add_subplot(gs[1])
    ax_C = fig.add_subplot(gs[2])

    # Subtle tinted backgrounds per panel
    ax_A.set_facecolor("#f8faff")
    ax_B.set_facecolor("#f8fff9")
    ax_C.set_facecolor("#fff9f8")
    for ax in (ax_A, ax_B, ax_C):
        for sp in ax.spines.values():
            sp.set_visible(False)

    panel_A(ax_A)
    panel_B(ax_B, org)
    panel_C(ax_C)

    fig.suptitle(
        "LEMONOIDS — Organism generation, anatomy, and disease model",
        fontsize=15, fontweight="bold", y=0.97, color=TXT,
    )

    out = Path(__file__).resolve().parent / "fig_organism_methods.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"[methods_fig] saved → {out.name}")
    plt.close(fig)


if __name__ == "__main__":
    main()
