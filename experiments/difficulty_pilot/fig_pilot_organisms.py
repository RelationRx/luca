#!/usr/bin/env python3
"""Side-by-side organism comparison: easy / medium / hard difficulty tiers.

Layout: 3 columns × 2 rows
  Row 1: GRN — module blobs, edges, malfunction gene (amber), latent genes (hatched/grey)
  Row 2: Phenotype bars — healthy (grey) vs disease (coloured); aberrant marked with ✕

Run from repo root:
    python experiments/difficulty_pilot/fig_pilot_organisms.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from luca.generation import generate_disease_organism, DIFFICULTY_PRESETS
from luca.dynamics import compute_phenotypes
from luca.inspect import MODULE_HEX

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DIFFICULTIES = ["easy", "medium", "hard"]
N_GENES      = 20
SEED         = 0
N_MODULES    = 4
N_SIGNALS    = 3
N_PHENOTYPES = 3

BG       = "#0d0d1a"
PANEL_BG = "#111122"

TIER_LABELS = {
    "easy":   "EASY\nprokaryote-like",
    "medium": "MEDIUM\nsimple eukaryote",
    "hard":   "HARD\ncomplex eukaryote",
}
TIER_COLORS = {
    "easy":   "#58a6ff",
    "medium": "#3fb950",
    "hard":   "#f85149",
}

PILOT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Generate organisms
# ---------------------------------------------------------------------------

orgs = {
    d: generate_disease_organism(
        n_genes=N_GENES, n_modules=N_MODULES, n_signals=N_SIGNALS,
        n_phenotypes=N_PHENOTYPES, difficulty=d, seed=SEED,
    )
    for d in DIFFICULTIES
}

# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

fig = plt.figure(figsize=(21, 13), facecolor=BG)
fig.patch.set_facecolor(BG)

fig.text(
    0.5, 0.985,
    "LUCA — Organism Difficulty Tiers  ·  n_genes=20, seed=0",
    ha="center", va="top",
    color="#FFC107", fontsize=14, fontweight="bold",
)

# 2 rows × 3 cols; a thin gap row between them
gs = fig.add_gridspec(
    2, 3,
    height_ratios=[1.55, 1.0],
    hspace=0.22, wspace=0.06,
    left=0.03, right=0.97,
    top=0.92, bottom=0.05,
)

# ---------------------------------------------------------------------------
# Shared spring layout: same seed → reproducible, comparable layout
# ---------------------------------------------------------------------------
# We build a dummy graph with all 20 genes to get consistent positions
_dummy_org = orgs["medium"]  # any org, just for node positions
_G0 = nx.DiGraph()
for g in _dummy_org.genes:
    _G0.add_node(g.id)
SHARED_POS = nx.spring_layout(_G0, seed=SEED * 7 + 3, k=1.8)


def draw_tier(ax_grn, ax_ph, org, difficulty):
    preset   = DIFFICULTY_PRESETS[difficulty]
    tier_col = TIER_COLORS[difficulty]

    gene_id_to_name = {g.id: g.name for g in org.genes}
    gene_id_to_mod  = {
        gid: k
        for k, mod in enumerate(org.modules)
        for gid in mod.gene_ids
    }
    observable_set = set(org.observable_genes)
    latent_set     = set(org.latent_genes)
    malfunction_ids = {
        m.target for m in org.malfunctions
        if any(g.id == m.target for g in org.genes)
    }

    # ── 1. GRN panel ─────────────────────────────────────────────────────────
    ax_grn.set_facecolor(PANEL_BG)

    G = nx.DiGraph()
    for g in org.genes:
        G.add_node(g.id)
    for r in org.relations:
        G.add_edge(r.src, r.dst, weight=r.strength, etype=r.type)

    pos = {gid: SHARED_POS.get(gid, np.zeros(2)) for gid in gene_id_to_name}

    # Module blobs
    for k, mod in enumerate(org.modules):
        member_ids = [gid for gid in mod.gene_ids if gid in pos]
        if not member_ids:
            continue
        pts = np.array([pos[gid] for gid in member_ids])
        cx, cy = pts.mean(axis=0)
        rx = (float(np.abs(pts[:, 0] - cx).max()) + 0.18 if len(pts) > 1 else 0.18) * 1.15
        ry = (float(np.abs(pts[:, 1] - cy).max()) + 0.18 if len(pts) > 1 else 0.18) * 1.05
        ax_grn.add_patch(mpatches.Ellipse(
            (cx, cy), width=rx * 2, height=ry * 2,
            facecolor=MODULE_HEX[k % len(MODULE_HEX)],
            edgecolor=MODULE_HEX[k % len(MODULE_HEX)],
            alpha=0.12, linewidth=2, linestyle="--", zorder=0,
        ))
        ax_grn.text(cx, cy + ry * 0.82, mod.label,
                    color=MODULE_HEX[k % len(MODULE_HEX)],
                    fontsize=6, ha="center", va="bottom",
                    alpha=0.7, style="italic", zorder=1)

    # Edges (grey for edges involving latent genes)
    act_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "activates"]
    inh_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "inhibits"]

    def edge_alpha(u, v):
        return 0.18 if (u in latent_set or v in latent_set) else 0.52

    for u, v in act_edges:
        nx.draw_networkx_edges(
            G, pos, ax=ax_grn, edgelist=[(u, v)],
            edge_color="#00e676",
            width=G[u][v]["weight"] * 1.5,
            alpha=edge_alpha(u, v),
            arrows=True, arrowsize=10,
            connectionstyle="arc3,rad=0.12",
        )
    for u, v in inh_edges:
        nx.draw_networkx_edges(
            G, pos, ax=ax_grn, edgelist=[(u, v)],
            edge_color="#ff4444",
            width=G[u][v]["weight"] * 1.5,
            alpha=edge_alpha(u, v),
            arrows=True, arrowsize=10,
            style="dashed",
            connectionstyle="arc3,rad=0.12",
        )

    # Nodes
    node_colors, node_sizes, node_edgecolors, node_alphas = [], [], [], []
    for g in org.genes:
        if g.id in malfunction_ids:
            node_colors.append("#FF6F00")
            node_sizes.append(620)
            node_edgecolors.append("#EF5350")
            node_alphas.append(0.95)
        elif g.id in latent_set:
            node_colors.append("#555566")
            node_sizes.append(200)
            node_edgecolors.append("#888")
            node_alphas.append(0.55)
        else:
            node_colors.append(MODULE_HEX[gene_id_to_mod.get(g.id, 0) % len(MODULE_HEX)])
            node_sizes.append(480 if g.id in observable_set else 250)
            node_edgecolors.append("white" if g.id in observable_set else "#444")
            node_alphas.append(0.90)

    nx.draw_networkx_nodes(
        G, pos, ax=ax_grn,
        node_color=node_colors, node_size=node_sizes,
        linewidths=1.4, edgecolors=node_edgecolors,
    )
    # Apply alpha per-node via scatter (networkx doesn't support per-node alpha natively)

    # Labels: hide latent gene names
    visible_labels = {
        g.id: gene_id_to_name[g.id]
        for g in org.genes
        if g.id not in latent_set
    }
    nx.draw_networkx_labels(
        G, pos, ax=ax_grn,
        labels=visible_labels,
        font_size=7, font_color="white", font_weight="bold",
    )
    # Latent: show "?" label in dim
    latent_labels = {g.id: "?" for g in org.genes if g.id in latent_set}
    if latent_labels:
        nx.draw_networkx_labels(
            G, pos, ax=ax_grn,
            labels=latent_labels,
            font_size=7, font_color="#888",
        )

    # Signals
    all_pts = np.array(list(pos.values()))
    centroid = all_pts.mean(axis=0)
    for sig in org.signals:
        is_chronic = any(m.target == sig.id and m.type == "PERSIST" for m in org.malfunctions)
        sc = "#EF5350" if is_chronic else "#FFD54F"
        if sig.targets and sig.targets[0] in pos:
            tp = np.array(pos[sig.targets[0]])
            d  = tp - centroid
            n  = np.linalg.norm(d)
            sig_pos = tp + (d / n if n > 0 else d) * 0.33
        else:
            sig_pos = centroid + np.array([0.45, 0.45])
        ax_grn.scatter(*sig_pos, s=240, marker="D", color=sc,
                       edgecolors="white", linewidths=0.8, alpha=0.88, zorder=5)
        ax_grn.text(sig_pos[0], sig_pos[1] + 0.065,
                    ("⚡" if is_chronic else "") + sig.label[:12],
                    color=sc, fontsize=5.8, ha="center", va="bottom",
                    fontweight="bold", zorder=6)
        ec = "#00e676" if sig.mode == "activates" else "#ff4444"
        for tgt in sig.targets:
            if tgt in pos:
                ax_grn.annotate(
                    "", xy=np.array(pos[tgt]), xytext=sig_pos,
                    arrowprops=dict(arrowstyle="->", color=ec, lw=1.2,
                                    alpha=0.6, connectionstyle="arc3,rad=0.15"),
                    zorder=4,
                )

    ax_grn.set_facecolor(PANEL_BG)
    ax_grn.axis("off")

    # Tier header box
    m0 = org.malfunctions[0] if org.malfunctions else None
    n_edges    = len(org.relations)
    n_feedback = preset["n_feedback"]
    n_latent   = len(org.latent_genes)
    stats = (
        f"edges={n_edges}  feedback={n_feedback}  "
        f"latent={n_latent}  steepness={preset['sigmoid_steepness']}\n"
        f"malfunction: {m0.type}/{m0.target_name}" if m0 else ""
    )
    ax_grn.set_title(
        f"{TIER_LABELS[difficulty]}\n{stats}",
        color=tier_col, fontsize=9.5, pad=6, fontweight="bold",
        loc="center",
    )

    # Small legend inside GRN
    legend_handles = []
    if malfunction_ids:
        legend_handles.append(mpatches.Patch(color="#FF6F00", label="malfunction gene"))
    if latent_set:
        legend_handles.append(mpatches.Patch(color="#555566", alpha=0.8, label=f"latent ({n_latent} genes)"))
    legend_handles += [
        mpatches.Patch(color="#00e676", label="activates"),
        mpatches.Patch(color="#ff4444", label="inhibits"),
    ]
    ax_grn.legend(handles=legend_handles, loc="lower left", fontsize=6,
                  facecolor="#1a1a2e", edgecolor="#333",
                  labelcolor="white", framealpha=0.85)

    # ── 2. Phenotype panel ───────────────────────────────────────────────────
    ax_ph.set_facecolor(PANEL_BG)

    disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    healthy_phenos = compute_phenotypes(org, org.healthy_baseline, noise=False) if org.healthy_baseline else {}

    ph_labels  = [ph.label for ph in org.phenotypes]
    ph_healthy = [healthy_phenos.get(l, 0.5) for l in ph_labels]
    ph_disease = [disease_phenos.get(l, 0.5) for l in ph_labels]
    ph_ranges  = [org.healthy_phenotype_ranges.get(l, (0.0, 1.0)) for l in ph_labels]

    n_ph   = len(ph_labels)
    y_pos  = list(range(n_ph - 1, -1, -1))
    bh     = 0.3

    ph_palette = ["#80DEEA", "#A5D6A7", "#FFF176", "#FFAB91", "#CE93D8"]

    for j, (y, lbl, hv, dv, (lo, hi)) in enumerate(zip(y_pos, ph_labels, ph_healthy, ph_disease, ph_ranges)):
        is_aberrant = not (lo <= dv <= hi)
        ph_col = "#EF5350" if is_aberrant else ph_palette[j % len(ph_palette)]

        # Healthy range span
        ax_ph.axvspan(lo, hi, ymin=(y - bh * 1.3 + 0.5) / (n_ph + 0.5),
                      ymax=(y + bh * 1.3 + 0.5) / (n_ph + 0.5),
                      color="#ffffff", alpha=0.05, zorder=0)

        # Healthy bar
        ax_ph.barh(y + bh * 0.55, hv, color="#888", alpha=0.55, height=bh * 0.9, zorder=2)
        # Disease bar
        ax_ph.barh(y - bh * 0.55, dv, color=ph_col, alpha=0.85, height=bh * 0.9, zorder=2)

        # Value labels
        ax_ph.text(max(hv, dv) + 0.02, y, f"H:{hv:.2f}  D:{dv:.2f}",
                   color="#ccc", fontsize=7, va="center")
        if is_aberrant:
            ax_ph.text(-0.03, y - bh * 0.55, "✕", color="#EF5350",
                       fontsize=10, va="center", ha="right", fontweight="bold")
        # Range brackets
        ax_ph.text(lo, y + bh * 1.4, f"{lo:.2f}", color="#555",
                   fontsize=5.5, ha="center", va="bottom")
        ax_ph.text(hi, y + bh * 1.4, f"{hi:.2f}", color="#555",
                   fontsize=5.5, ha="center", va="bottom")

    ax_ph.set_yticks(y_pos)
    ax_ph.set_yticklabels(ph_labels, fontsize=8.5, color="#CE93D8")
    ax_ph.set_xlim(-0.12, 1.28)
    ax_ph.axvline(0.5, color="#ffffff15", linewidth=1, linestyle="--")
    ax_ph.set_xlabel("Phenotype activity", color="#888", fontsize=8)
    ax_ph.tick_params(colors="white")
    for sp in ("top", "right"):
        ax_ph.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax_ph.spines[sp].set_edgecolor("#333")

    # Mini legend
    leg_ph = [
        mpatches.Patch(color="#888", alpha=0.6, label="healthy"),
        mpatches.Patch(color=ph_palette[0], label="disease (in range)"),
        mpatches.Patch(color="#EF5350", label="disease (aberrant)"),
    ]
    ax_ph.legend(handles=leg_ph, loc="lower right", fontsize=6,
                 facecolor="#1a1a2e", edgecolor="#333",
                 labelcolor="white", framealpha=0.85)
    ax_ph.set_title("Phenotypes: healthy vs disease",
                    color="#aaa", fontsize=8, pad=4)


# ---------------------------------------------------------------------------
# Draw all three tiers
# ---------------------------------------------------------------------------

for col, diff in enumerate(DIFFICULTIES):
    ax_grn = fig.add_subplot(gs[0, col])
    ax_ph  = fig.add_subplot(gs[1, col])
    draw_tier(ax_grn, ax_ph, orgs[diff], diff)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

out_path = PILOT_DIR / "fig_pilot_organisms.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out_path}")
plt.close()
