"""LEMONS organism inspector — terminal (rich) + matplotlib graph."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import Organism

# ---------------------------------------------------------------------------
# Terminal inspector
# ---------------------------------------------------------------------------

MODULE_COLORS = ["green", "blue", "magenta", "cyan", "yellow", "red"]
MODULE_HEX = ["#4CAF50", "#2196F3", "#CE93D8", "#00BCD4", "#FFC107", "#EF5350"]


def print_organism(org: "Organism") -> None:
    """Rich terminal inspector. Falls back to plain text if rich is not installed."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
        _print_rich(org, Console())
    except ImportError:
        _print_plain(org)


def _bar(val: float, width: int = 10) -> str:
    filled = round(val * width)
    return "█" * filled + "░" * (width - filled)


def _print_rich(org: "Organism", console) -> None:
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    from .dynamics import compute_phenotypes

    observable_set = set(org.observable_genes)
    n_edges = len(org.relations)
    gene_id_to_mod: dict[str, int] = {}
    for k, mod in enumerate(org.modules):
        for gid in mod.gene_ids:
            gene_id_to_mod[gid] = k
    gene_id_to_name = {g.id: g.name for g in org.genes}

    # ── Header ──────────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold yellow]🍋 LEMONS[/bold yellow]  [dim white]{org.id}[/dim white]\n"
        f"  seed [cyan]{org.seed}[/cyan]  ·  "
        f"[bold green]{len(org.genes)}[/bold green] genes  ·  "
        f"[bold blue]{len(org.modules)}[/bold blue] modules  ·  "
        f"[bold white]{n_edges}[/bold white] edges  ·  "
        f"[bold yellow]{len(org.signals)}[/bold yellow] signals  ·  "
        f"[bold magenta]{len(org.phenotypes)}[/bold magenta] phenotypes  ·  "
        f"[dim]{len(observable_set)}/{len(org.genes)} observable[/dim]",
        border_style="yellow",
        expand=False,
        padding=(0, 2),
    ))

    # ── Modules ──────────────────────────────────────────────────────────────
    mt = Table(title="🗂️  Modules", box=box.ROUNDED, border_style="dim white",
               title_style="bold white", show_header=True, header_style="dim")
    mt.add_column("ID", style="dim", width=6)
    mt.add_column("Label", min_width=26)
    mt.add_column("Genes")
    for k, mod in enumerate(org.modules):
        c = MODULE_COLORS[k % len(MODULE_COLORS)]
        names = [g.name for g in org.genes if g.id in mod.gene_ids]
        mt.add_row(
            mod.id,
            f"[{c}]{mod.label}[/{c}]",
            "  ".join(f"[{c}]{n}[/{c}]" for n in names),
        )
    console.print(mt)

    # ── Gene states ──────────────────────────────────────────────────────────
    gt = Table(title="🧬 Baseline Gene States", box=box.ROUNDED, border_style="dim white",
               title_style="bold white", show_header=True, header_style="dim")
    gt.add_column("Gene", width=6)
    gt.add_column("Module", min_width=24)
    gt.add_column("State")
    gt.add_column("", width=3, justify="center")
    for g in org.genes:
        val = org.baseline_state.get(g.id, 0.0)
        k = gene_id_to_mod.get(g.id, 0)
        c = MODULE_COLORS[k % len(MODULE_COLORS)]
        mod_label = org.modules[k].label if k < len(org.modules) else "?"
        bar_color = "green" if val > 0.5 else "red"
        gt.add_row(
            f"[bold]{g.name}[/bold]",
            f"[{c}]{mod_label}[/{c}]",
            f"[{bar_color}]{_bar(val)}[/{bar_color}]  [white]{val:.2f}[/white]",
            "👁" if g.id in observable_set else "[dim]·[/dim]",
        )
    console.print(gt)

    # ── Signals ──────────────────────────────────────────────────────────────
    st = Table(title="📡 Signals", box=box.ROUNDED, border_style="dim white",
               title_style="bold white", show_header=True, header_style="dim")
    st.add_column("Label", min_width=20)
    st.add_column("Mode", width=11)
    st.add_column("Targets")
    st.add_column("Strength", width=9, justify="right")
    for sig in org.signals:
        mode_str = "[green]activates[/green]" if sig.mode == "activates" else "[red]inhibits[/red]"
        targets = ", ".join(gene_id_to_name.get(t, t) for t in sig.targets)
        st.add_row(f"[yellow]{sig.label}[/yellow]", mode_str, targets, f"{sig.strength:.3f}")
    console.print(st)

    # ── Phenotypes ───────────────────────────────────────────────────────────
    baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    pt = Table(title="📊 Phenotypes (baseline)", box=box.ROUNDED, border_style="dim white",
               title_style="bold white", show_header=True, header_style="dim")
    pt.add_column("Label", min_width=18)
    pt.add_column("Value")
    pt.add_column("Depends on")
    for ph in org.phenotypes:
        val = baseline_phenos.get(ph.label, 0.0)
        bar_color = "green" if val > 0.5 else "red"
        dep_names = [gene_id_to_name.get(g, g) for g in ph.readout.depends_on]
        pt.add_row(
            f"[bold magenta]{ph.label}[/bold magenta]",
            f"[{bar_color}]{_bar(val)}[/{bar_color}]  [white]{val:.2f}[/white]",
            "  ".join(dep_names),
        )
    console.print(pt)


def _print_plain(org: "Organism") -> None:
    from .dynamics import compute_phenotypes

    observable_set = set(org.observable_genes)
    print(f"\n🍋 LEMONS  {org.id}  seed={org.seed}")
    print(f"  {len(org.genes)} genes · {len(org.modules)} modules · "
          f"{len(org.relations)} edges · {len(org.signals)} signals · "
          f"{len(org.phenotypes)} phenotypes · "
          f"{len(observable_set)}/{len(org.genes)} observable\n")

    print("Modules:")
    for mod in org.modules:
        names = [g.name for g in org.genes if g.id in mod.gene_ids]
        print(f"  {mod.id}  {mod.label:<28}  {' '.join(names)}")

    print("\nBaseline Gene States:")
    gene_id_to_mod = {gid: k for k, m in enumerate(org.modules) for gid in m.gene_ids}
    for g in org.genes:
        val = org.baseline_state.get(g.id, 0.0)
        eye = "👁" if g.id in observable_set else " "
        print(f"  {g.name}  {_bar(val)} {val:.2f}  {eye}")

    print("\nSignals:")
    gene_id_to_name = {g.id: g.name for g in org.genes}
    for sig in org.signals:
        targets = ", ".join(gene_id_to_name.get(t, t) for t in sig.targets)
        print(f"  {sig.label:<22} {sig.mode:<10} → {targets}  str={sig.strength:.2f}")

    baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    print("\nPhenotypes (baseline):")
    for ph in org.phenotypes:
        val = baseline_phenos.get(ph.label, 0.0)
        print(f"  {ph.label:<20} {_bar(val)} {val:.2f}")
    print()


# ---------------------------------------------------------------------------
# Matplotlib graph
# ---------------------------------------------------------------------------

def plot_organism(
    org: "Organism",
    save_path: str | None = None,
    show: bool = True,
) -> None:
    """
    Two-panel matplotlib figure:
    - Left:  GRN network with module blobs and colored edges
    - Right: Horizontal bar chart of baseline gene states + phenotypes
    """
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import networkx as nx
        import numpy as np
    except ImportError as e:
        print(f"[inspect] Missing dependency: {e}. Install with: pip install matplotlib networkx")
        return

    from .dynamics import compute_phenotypes

    # ── Shared data ──────────────────────────────────────────────────────────
    gene_id_to_name = {g.id: g.name for g in org.genes}
    gene_id_to_mod: dict[str, int] = {}
    for k, mod in enumerate(org.modules):
        for gid in mod.gene_ids:
            gene_id_to_mod[gid] = k
    observable_set = set(org.observable_genes)
    baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)

    # ── Figure ───────────────────────────────────────────────────────────────
    BG = "#0d0d1a"
    PANEL_BG = "#111122"
    fig, (ax_grn, ax_bar) = plt.subplots(1, 2, figsize=(20, 9))
    fig.patch.set_facecolor(BG)
    for ax in (ax_grn, ax_bar):
        ax.set_facecolor(PANEL_BG)

    fig.suptitle(
        f"LEMONS  ·  {org.id}  ·  seed={org.seed}",
        color="#FFC107", fontsize=14, fontweight="bold", y=0.99,
    )

    # ── Build graph ──────────────────────────────────────────────────────────
    G = nx.DiGraph()
    for g in org.genes:
        G.add_node(g.id)
    for r in org.relations:
        G.add_edge(r.src, r.dst, weight=r.strength, etype=r.type)

    pos = nx.spring_layout(G, seed=org.seed, k=2.2)

    # ── Module blobs (funky background ellipses) ─────────────────────────────
    for k, mod in enumerate(org.modules):
        member_ids = [gid for gid in mod.gene_ids if gid in pos]
        if not member_ids:
            continue
        pts = np.array([pos[gid] for gid in member_ids])
        cx, cy = pts.mean(axis=0)
        if len(pts) == 1:
            rx, ry = 0.18, 0.18
        else:
            rx = float(np.abs(pts[:, 0] - cx).max()) + 0.18
            ry = float(np.abs(pts[:, 1] - cy).max()) + 0.18
        # Slightly different x/y radii for an organic feel
        rx *= 1.15
        ry *= 1.05
        ellipse = mpatches.Ellipse(
            (cx, cy), width=rx * 2, height=ry * 2,
            facecolor=MODULE_HEX[k % len(MODULE_HEX)],
            edgecolor=MODULE_HEX[k % len(MODULE_HEX)],
            alpha=0.13, linewidth=2.5, linestyle="--",
            zorder=0,
        )
        ax_grn.add_patch(ellipse)
        # Module label inside blob
        ax_grn.text(
            cx, cy + ry * 0.82, mod.label,
            color=MODULE_HEX[k % len(MODULE_HEX)], fontsize=6.5,
            ha="center", va="bottom", alpha=0.75,
            style="italic", zorder=1,
        )

    # ── Edges ────────────────────────────────────────────────────────────────
    act_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "activates"]
    inh_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "inhibits"]

    nx.draw_networkx_edges(
        G, pos, ax=ax_grn, edgelist=act_edges,
        edge_color="#00e676",
        width=[G[u][v]["weight"] * 1.8 for u, v in act_edges],
        alpha=0.55, arrows=True, arrowsize=14,
        connectionstyle="arc3,rad=0.12",
    )
    nx.draw_networkx_edges(
        G, pos, ax=ax_grn, edgelist=inh_edges,
        edge_color="#ff4444",
        width=[G[u][v]["weight"] * 1.8 for u, v in inh_edges],
        alpha=0.55, arrows=True, arrowsize=14, style="dashed",
        connectionstyle="arc3,rad=0.12",
    )

    # ── Gene nodes ───────────────────────────────────────────────────────────
    node_colors = [MODULE_HEX[gene_id_to_mod.get(g.id, 0) % len(MODULE_HEX)] for g in org.genes]
    node_sizes = [520 if g.id in observable_set else 280 for g in org.genes]
    nx.draw_networkx_nodes(
        G, pos, ax=ax_grn,
        node_color=node_colors, node_size=node_sizes,
        alpha=0.92, linewidths=1.5,
        edgecolors=["white" if g.id in observable_set else "#555" for g in org.genes],
    )
    nx.draw_networkx_labels(
        G, pos, ax=ax_grn,
        labels=gene_id_to_name, font_size=7.5, font_color="white",
        font_weight="bold",
    )

    # ── Signal nodes ─────────────────────────────────────────────────────────
    import numpy as np
    for sig in org.signals:
        # Place signal node near its first target, offset outward from centroid
        all_positions = np.array(list(pos.values()))
        centroid = all_positions.mean(axis=0)
        if sig.targets and sig.targets[0] in pos:
            tp = np.array(pos[sig.targets[0]])
            direction = tp - centroid
            norm = np.linalg.norm(direction)
            if norm > 0:
                direction = direction / norm
            sig_pos = tp + direction * 0.35
        else:
            sig_pos = centroid + np.array([0.5, 0.5])

        sc = "#FFD54F"
        ax_grn.scatter(*sig_pos, s=320, marker="D", color=sc, alpha=0.9,
                       edgecolors="white", linewidths=1, zorder=5)
        ax_grn.text(sig_pos[0], sig_pos[1] + 0.07, sig.label,
                    color=sc, fontsize=6.5, ha="center", va="bottom",
                    fontweight="bold", zorder=6)
        # Arrow to each target
        edge_color = "#00e676" if sig.mode == "activates" else "#ff4444"
        for tgt in sig.targets:
            if tgt in pos:
                tp = np.array(pos[tgt])
                ax_grn.annotate(
                    "", xy=tp, xytext=sig_pos,
                    arrowprops=dict(
                        arrowstyle="->", color=edge_color,
                        lw=1.5, alpha=0.7,
                        connectionstyle="arc3,rad=0.15",
                    ),
                    zorder=4,
                )

    # ── Legend ───────────────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(color=MODULE_HEX[k % len(MODULE_HEX)], label=mod.label, alpha=0.85)
        for k, mod in enumerate(org.modules)
    ]
    legend_handles += [
        mpatches.Patch(color="#00e676", label="activates"),
        mpatches.Patch(color="#ff4444", label="inhibits"),
        mpatches.Patch(color="#FFD54F", label="signal"),
    ]
    ax_grn.legend(
        handles=legend_handles, loc="lower left", fontsize=7,
        facecolor="#1a1a2e", edgecolor="#555", labelcolor="white",
        framealpha=0.85,
    )
    ax_grn.set_title("Gene Regulatory Network", color="white", fontsize=12, pad=10)
    ax_grn.axis("off")

    # ── Right panel: gene state bars ─────────────────────────────────────────
    gene_names = [g.name for g in org.genes]
    gene_vals = [org.baseline_state.get(g.id, 0.0) for g in org.genes]
    bar_colors = [MODULE_HEX[gene_id_to_mod.get(g.id, 0) % len(MODULE_HEX)] for g in org.genes]

    n_genes = len(org.genes)
    n_phenos = len(org.phenotypes)
    total_rows = n_genes + 1 + n_phenos  # genes + separator gap + phenotypes

    gene_y = list(range(n_genes - 1, -1, -1))  # top to bottom
    pheno_y = [-(i + 2) for i in range(n_phenos)]  # below separator

    ax_bar.barh(gene_y, gene_vals, color=bar_colors, alpha=0.85, height=0.72, zorder=2)

    # Observable eye marker
    for i, (g, y) in enumerate(zip(org.genes, gene_y)):
        if g.id in observable_set:
            ax_bar.text(1.04, y, "[obs]", fontsize=7, va="center", color="#aaa")

    ax_bar.set_yticks(gene_y)
    ax_bar.set_yticklabels(gene_names, fontsize=8.5, color="white")

    # Separator line
    sep_y = -0.8
    ax_bar.axhline(sep_y, color="#444", linewidth=1, linestyle="--")
    ax_bar.text(0.5, sep_y - 0.35, "phenotypes", color="#888", fontsize=7.5,
                ha="center", va="top", style="italic")

    # Phenotype bars
    ph_labels = [ph.label for ph in org.phenotypes]
    ph_vals = [baseline_phenos.get(ph.label, 0.0) for ph in org.phenotypes]
    ph_colors = ["#CE93D8", "#80DEEA", "#A5D6A7", "#FFF176", "#FFAB91"]
    for y, label, val, col in zip(pheno_y, ph_labels, ph_vals, ph_colors):
        ax_bar.barh(y, val, color=col, alpha=0.8, height=0.65, zorder=2)
        ax_bar.text(val + 0.02, y, f"{val:.2f}", color="white", fontsize=8,
                    va="center", zorder=3)

    ax_bar.set_yticks(list(ax_bar.get_yticks()) + pheno_y)
    all_labels = [t.get_text() for t in ax_bar.get_yticklabels()]
    # Rebuild yticklabels properly
    ax_bar.set_yticks(gene_y + pheno_y)
    ax_bar.set_yticklabels(gene_names + ph_labels, fontsize=8.5, color="white")

    ax_bar.set_xlim(0, 1.12)
    ax_bar.set_xlabel("Activity (0 – 1)", color="#aaa", fontsize=9)
    ax_bar.axvline(0.5, color="#ffffff22", linewidth=1, linestyle="--", zorder=1)
    ax_bar.set_title("Baseline States & Phenotypes", color="white", fontsize=12, pad=10)
    ax_bar.tick_params(colors="white")
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    for spine in ("bottom", "left"):
        ax_bar.spines[spine].set_edgecolor("#444")

    plt.tight_layout(rect=[0, 0, 1, 0.97])

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
        print(f"[inspect] Saved → {save_path}")
    if show:
        plt.show()
    plt.close()
