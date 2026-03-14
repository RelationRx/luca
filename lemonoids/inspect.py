"""LEMONOIDS organism inspector — terminal (rich) + matplotlib graph."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import Organism
    from .experiment import ExperimentSession

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
        f"[bold yellow]🍋 LEMONOIDS[/bold yellow]  [dim white]{org.id}[/dim white]\n"
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
    print(f"\n🍋 LEMONOIDS  {org.id}  seed={org.seed}")
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
        f"LEMONOIDS  ·  {org.id}  ·  seed={org.seed}",
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


# ---------------------------------------------------------------------------
# Disease organism comparison plot
# ---------------------------------------------------------------------------

def plot_disease_organism(
    org: "Organism",
    save_path: str | None = None,
    show: bool = True,
    rescue_interventions: dict | None = None,
) -> None:
    """
    Two-panel figure comparing healthy vs disease states (and optionally rescue):
    - Left:  GRN network — malfunctioning genes/signals highlighted
    - Right: Grouped bars per gene/phenotype: grey=healthy, red/green=disease, teal=rescued
             Healthy range shown as a faint span; aberrant rows marked with !

    rescue_interventions: {gene_name: {"type": "BLOCK"|"BOOST"|"DAMPEN"}} passed to simulate_sigmoid.
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

    if not org.malfunctions:
        print("[inspect] plot_disease_organism: organism has no malfunctions; using plot_organism instead.")
        plot_organism(org, save_path=save_path, show=show)
        return

    from .dynamics import compute_phenotypes, simulate_sigmoid

    # ── Shared data ──────────────────────────────────────────────────────────
    gene_id_to_name = {g.id: g.name for g in org.genes}
    name_to_id = {g.name: g.id for g in org.genes}
    gene_id_to_mod: dict[str, int] = {}
    for k, mod in enumerate(org.modules):
        for gid in mod.gene_ids:
            gene_id_to_mod[gid] = k

    # Compute rescue state if interventions provided
    rescue_gene_state: dict[str, float] = {}
    rescue_phenos: dict[str, float] = {}
    if rescue_interventions:
        gene_ivs = {name_to_id[n]: v for n, v in rescue_interventions.items() if n in name_to_id}
        res = simulate_sigmoid(org, interventions=gene_ivs, active_signals={},
                               rng=np.random.default_rng(0))
        rescue_gene_state = res["final_state"]
        rescue_phenos = compute_phenotypes(org, rescue_gene_state, noise=False)
    observable_set = set(org.observable_genes)

    disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    healthy_phenos = compute_phenotypes(org, org.healthy_baseline, noise=False) if org.healthy_baseline else {}

    # ── Figure ───────────────────────────────────────────────────────────────
    BG = "#0d0d1a"
    PANEL_BG = "#111122"
    HEALTHY_COLOR = "#888888"
    DISEASE_COLOR_OK = "#4CAF50"
    DISEASE_COLOR_ABERRANT = "#EF5350"

    ct_label = org.cell_type.label if org.cell_type else "unknown cell type"
    malfunction_strs = "; ".join(m.description for m in org.malfunctions)

    fig, (ax_grn, ax_bar) = plt.subplots(1, 2, figsize=(22, 10))
    fig.patch.set_facecolor(BG)
    for ax in (ax_grn, ax_bar):
        ax.set_facecolor(PANEL_BG)

    fig.suptitle(
        f"LEMONOIDS Disease  ·  {org.id}  ·  {ct_label}  ·  seed={org.seed}\n"
        f"Malfunction: {malfunction_strs}",
        color="#EF5350", fontsize=11, fontweight="bold", y=0.99,
    )

    # ── Build GRN (left panel — same as plot_organism) ────────────────────
    G = nx.DiGraph()
    for g in org.genes:
        G.add_node(g.id)
    for r in org.relations:
        G.add_edge(r.src, r.dst, weight=r.strength, etype=r.type)

    pos = nx.spring_layout(G, seed=org.seed, k=2.2)

    for k, mod in enumerate(org.modules):
        member_ids = [gid for gid in mod.gene_ids if gid in pos]
        if not member_ids:
            continue
        pts = np.array([pos[gid] for gid in member_ids])
        cx, cy = pts.mean(axis=0)
        rx = float(np.abs(pts[:, 0] - cx).max()) + 0.18 if len(pts) > 1 else 0.18
        ry = float(np.abs(pts[:, 1] - cy).max()) + 0.18 if len(pts) > 1 else 0.18
        rx *= 1.15
        ry *= 1.05
        ellipse = mpatches.Ellipse(
            (cx, cy), width=rx * 2, height=ry * 2,
            facecolor=MODULE_HEX[k % len(MODULE_HEX)],
            edgecolor=MODULE_HEX[k % len(MODULE_HEX)],
            alpha=0.13, linewidth=2.5, linestyle="--", zorder=0,
        )
        ax_grn.add_patch(ellipse)
        ax_grn.text(
            cx, cy + ry * 0.82, mod.label,
            color=MODULE_HEX[k % len(MODULE_HEX)], fontsize=6.5,
            ha="center", va="bottom", alpha=0.75, style="italic", zorder=1,
        )

    act_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "activates"]
    inh_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "inhibits"]
    nx.draw_networkx_edges(G, pos, ax=ax_grn, edgelist=act_edges, edge_color="#00e676",
                           width=[G[u][v]["weight"] * 1.8 for u, v in act_edges],
                           alpha=0.55, arrows=True, arrowsize=14,
                           connectionstyle="arc3,rad=0.12")
    nx.draw_networkx_edges(G, pos, ax=ax_grn, edgelist=inh_edges, edge_color="#ff4444",
                           width=[G[u][v]["weight"] * 1.8 for u, v in inh_edges],
                           alpha=0.55, arrows=True, arrowsize=14, style="dashed",
                           connectionstyle="arc3,rad=0.12")

    # Highlight malfunctioning genes/signal targets
    malfunction_gene_ids = {
        m.target for m in org.malfunctions
        if any(g.id == m.target for g in org.genes)
    }
    node_colors = []
    node_sizes = []
    node_edge_colors = []
    for g in org.genes:
        if g.id in malfunction_gene_ids:
            node_colors.append("#FF6F00")   # amber highlight for malfunctioning gene
            node_sizes.append(700)
            node_edge_colors.append("#EF5350")
        else:
            node_colors.append(MODULE_HEX[gene_id_to_mod.get(g.id, 0) % len(MODULE_HEX)])
            node_sizes.append(520 if g.id in observable_set else 280)
            node_edge_colors.append("white" if g.id in observable_set else "#555")

    nx.draw_networkx_nodes(G, pos, ax=ax_grn, node_color=node_colors,
                           node_size=node_sizes, alpha=0.92, linewidths=1.5,
                           edgecolors=node_edge_colors)
    nx.draw_networkx_labels(G, pos, ax=ax_grn, labels=gene_id_to_name,
                            font_size=7.5, font_color="white", font_weight="bold")

    for sig in org.signals:
        all_positions = np.array(list(pos.values()))
        centroid = all_positions.mean(axis=0)
        if sig.targets and sig.targets[0] in pos:
            tp = np.array(pos[sig.targets[0]])
            direction = tp - centroid
            norm = np.linalg.norm(direction)
            direction = direction / norm if norm > 0 else direction
            sig_pos = tp + direction * 0.35
        else:
            sig_pos = centroid + np.array([0.5, 0.5])

        # Highlight chronic signal malfunctions
        is_chronic = any(
            m.target == sig.id and m.type == "PERSIST" for m in org.malfunctions
        )
        sc = "#EF5350" if is_chronic else "#FFD54F"
        ax_grn.scatter(*sig_pos, s=320, marker="D", color=sc, alpha=0.9,
                       edgecolors="white", linewidths=1, zorder=5)
        prefix = "⚡" if is_chronic else ""
        ax_grn.text(sig_pos[0], sig_pos[1] + 0.07, f"{prefix}{sig.label}",
                    color=sc, fontsize=6.5, ha="center", va="bottom",
                    fontweight="bold", zorder=6)
        edge_color = "#00e676" if sig.mode == "activates" else "#ff4444"
        for tgt in sig.targets:
            if tgt in pos:
                ax_grn.annotate(
                    "", xy=np.array(pos[tgt]), xytext=sig_pos,
                    arrowprops=dict(arrowstyle="->", color=edge_color,
                                    lw=1.5, alpha=0.7,
                                    connectionstyle="arc3,rad=0.15"),
                    zorder=4,
                )

    legend_handles = [
        mpatches.Patch(color=MODULE_HEX[k % len(MODULE_HEX)], label=mod.label, alpha=0.85)
        for k, mod in enumerate(org.modules)
    ]
    legend_handles += [
        mpatches.Patch(color="#FF6F00", label="malfunctioning gene"),
        mpatches.Patch(color="#00e676", label="activates"),
        mpatches.Patch(color="#ff4444", label="inhibits"),
        mpatches.Patch(color="#FFD54F", label="signal"),
        mpatches.Patch(color="#EF5350", label="chronic signal"),
    ]
    ax_grn.legend(handles=legend_handles, loc="lower left", fontsize=7,
                  facecolor="#1a1a2e", edgecolor="#555", labelcolor="white", framealpha=0.85)
    ax_grn.set_title(f"GRN  ·  {ct_label}", color="white", fontsize=11, pad=10)
    ax_grn.axis("off")

    # ── Right panel: grouped bars — healthy / disease / (rescue) ─────────
    RESCUE_COLOR = "#26C6DA"   # teal

    gene_names = [g.name for g in org.genes]
    healthy_gene_vals = [org.healthy_baseline.get(g.id, 0.0) for g in org.genes]
    disease_gene_vals = [org.baseline_state.get(g.id, 0.0) for g in org.genes]
    rescue_gene_vals  = [rescue_gene_state.get(g.id, 0.0) for g in org.genes] if rescue_gene_state else []
    bar_colors = [MODULE_HEX[gene_id_to_mod.get(g.id, 0) % len(MODULE_HEX)] for g in org.genes]

    n_genes = len(org.genes)
    n_phenos = len(org.phenotypes)
    n_bars = 3 if rescue_interventions else 2

    bar_height = 0.28 if n_bars == 3 else 0.35
    gap = 1.0 if n_bars == 3 else 0.85

    # y positions: top = healthy, middle = disease, bottom = rescue (if present)
    def row_ys(center_i: int) -> list[float]:
        cy = center_i * gap
        if n_bars == 3:
            return [cy + bar_height, cy, cy - bar_height]
        return [cy + bar_height / 2, cy - bar_height / 2]

    gene_rows = [row_ys(i) for i in range(n_genes - 1, -1, -1)]

    # Gene bars
    for i, (g, ys, col) in enumerate(zip(org.genes, gene_rows, bar_colors)):
        ax_bar.barh(ys[0], healthy_gene_vals[i], color=HEALTHY_COLOR, alpha=0.55,
                    height=bar_height, zorder=2)
        ax_bar.barh(ys[1], disease_gene_vals[i], color=col, alpha=0.85,
                    height=bar_height, zorder=2)
        if n_bars == 3:
            ax_bar.barh(ys[2], rescue_gene_vals[i], color=RESCUE_COLOR, alpha=0.85,
                        height=bar_height, zorder=2)
        # Mark malfunctioning gene
        if g.id in malfunction_gene_ids:
            center_y = sum(ys) / len(ys)
            ax_bar.axhspan(min(ys) - bar_height * 0.1, max(ys) + bar_height * 0.1,
                           color="#FF6F00", alpha=0.08, zorder=0)
        if g.id in observable_set:
            ax_bar.text(1.04, sum(ys) / len(ys), "[obs]", fontsize=6, va="center", color="#aaa")

    tick_y = [sum(ys) / len(ys) for ys in gene_rows]
    ax_bar.set_yticks(tick_y)
    ax_bar.set_yticklabels(gene_names, fontsize=8, color="white")

    # Separator
    sep_y = min(gene_rows[-1]) - gap * 0.55
    ax_bar.axhline(sep_y, color="#444", linewidth=1, linestyle="--")
    ax_bar.text(0.5, sep_y - 0.28, "phenotypes", color="#888", fontsize=7.5,
                ha="center", va="top", style="italic")

    # Phenotype bars
    ph_labels = [ph.label for ph in org.phenotypes]
    ph_healthy_vals = [healthy_phenos.get(ph.label, 0.5) for ph in org.phenotypes]
    ph_disease_vals  = [disease_phenos.get(ph.label, 0.5) for ph in org.phenotypes]
    ph_rescue_vals   = [rescue_phenos.get(ph.label, 0.5) for ph in org.phenotypes] if rescue_phenos else []
    ph_colors_ok = ["#80DEEA", "#A5D6A7", "#FFF176", "#FFAB91", "#CE93D8"]

    base_ph_center = sep_y - gap * 1.1
    ph_rows = [row_ys(0)] * n_phenos  # placeholder
    for j in range(n_phenos):
        center = base_ph_center - j * gap
        ph_rows[j] = [center + bar_height * k for k in ([1, 0, -1] if n_bars == 3 else [0.5, -0.5])]

    ph_tick_y = [sum(ys) / len(ys) for ys in ph_rows]

    for i, (ph, ys) in enumerate(zip(org.phenotypes, ph_rows)):
        lo, hi = org.healthy_phenotype_ranges.get(ph.label, (0.0, 1.0))
        is_aberrant = not (lo <= ph_disease_vals[i] <= hi)
        is_rescued = n_bars == 3 and (lo <= ph_rescue_vals[i] <= hi)
        dis_color = DISEASE_COLOR_ABERRANT if is_aberrant else ph_colors_ok[i % len(ph_colors_ok)]

        # Healthy range span
        row_top = max(ys) + bar_height * 0.15
        row_bot = min(ys) - bar_height * 0.15
        ax_bar.fill_betweenx([row_bot, row_top], lo, hi, color="#ffffff", alpha=0.05, zorder=0)
        ax_bar.text(lo, max(ys) + bar_height * 0.55, f"[{lo:.2f}", color="#666",
                    fontsize=5.5, ha="left", va="bottom")
        ax_bar.text(hi, max(ys) + bar_height * 0.55, f"{hi:.2f}]", color="#666",
                    fontsize=5.5, ha="right", va="bottom")

        ax_bar.barh(ys[0], ph_healthy_vals[i], color=HEALTHY_COLOR, alpha=0.55,
                    height=bar_height, zorder=2)
        ax_bar.barh(ys[1], ph_disease_vals[i], color=dis_color, alpha=0.85,
                    height=bar_height, zorder=2)

        rightmost = max(ph_disease_vals[i], ph_healthy_vals[i])
        if n_bars == 3:
            ax_bar.barh(ys[2], ph_rescue_vals[i], color=RESCUE_COLOR, alpha=0.85,
                        height=bar_height, zorder=2)
            rightmost = max(rightmost, ph_rescue_vals[i])
            ax_bar.text(rightmost + 0.02, ys[2], f"{ph_rescue_vals[i]:.2f}",
                        color=RESCUE_COLOR, fontsize=7, va="center", zorder=3)

        ax_bar.text(rightmost + 0.02, ys[1], f"{ph_disease_vals[i]:.2f}",
                    color=dis_color, fontsize=7, va="center", zorder=3)

        if is_aberrant:
            ax_bar.text(-0.02, ys[1], "✕", color=DISEASE_COLOR_ABERRANT,
                        fontsize=9, va="center", ha="right", fontweight="bold", zorder=4)
        if n_bars == 3 and is_rescued and is_aberrant:
            ax_bar.text(-0.02, ys[2], "✓", color=RESCUE_COLOR,
                        fontsize=9, va="center", ha="right", fontweight="bold", zorder=4)

    ax_bar.set_yticks(list(tick_y) + ph_tick_y)
    ax_bar.set_yticklabels(gene_names + ph_labels, fontsize=8, color="white")

    ax_bar.set_xlim(-0.1, 1.22)
    ax_bar.set_xlabel("Activity (0 – 1)", color="#aaa", fontsize=9)
    ax_bar.axvline(0.5, color="#ffffff22", linewidth=1, linestyle="--", zorder=1)

    legend_bar = [
        mpatches.Patch(color=HEALTHY_COLOR, alpha=0.6, label="healthy"),
        mpatches.Patch(color="#4CAF50", label="disease (in range)"),
        mpatches.Patch(color=DISEASE_COLOR_ABERRANT, label="disease (aberrant)"),
    ]
    if rescue_interventions:
        rescue_label = "rescued: " + ", ".join(
            f"{n} {v.get('type','?')}" if isinstance(v, dict) else f"{n} {v}"
            for n, v in rescue_interventions.items()
        )
        legend_bar.append(mpatches.Patch(color=RESCUE_COLOR, label=rescue_label))
    ax_bar.legend(handles=legend_bar, loc="lower right", fontsize=7,
                  facecolor="#1a1a2e", edgecolor="#555", labelcolor="white", framealpha=0.85)
    title_suffix = " + Rescue" if rescue_interventions else ""
    ax_bar.set_title(f"Healthy vs Disease{title_suffix}", color="white", fontsize=11, pad=10)
    ax_bar.tick_params(colors="white")
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    for spine in ("bottom", "left"):
        ax_bar.spines[spine].set_edgecolor("#444")

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
        print(f"[inspect] Saved → {save_path}")
    if show:
        plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# Disease comparison — side-by-side healthy vs disease GRN
# ---------------------------------------------------------------------------

def plot_disease_comparison(
    org: "Organism",
    save_path: str | None = None,
    show: bool = True,
) -> None:
    """
    Side-by-side GRN comparison: left panel = healthy network, right panel = disease network.
    Both panels use the same graph layout so the malfunction and its downstream effects are
    immediately visible.

    Visual design:
    - Node colour = gene activity level (blue → red colormap)
    - Disease panel: malfunction gene(s) get a thick red border + type label near the node
    - Genes that shifted significantly (|Δ| > 0.1) get a white asterisk in the disease panel
    - Module blobs, signal diamonds, edge colours — same style as plot_organism
    - Suptitle: "Healthy vs Disease — {cell_type} — {malfunction description}"

    ``org`` must be a disease Organism (has .healthy_baseline, .baseline_state, .malfunctions).
    """
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import matplotlib.colors as mcolors
        import matplotlib.gridspec as gridspec
        import networkx as nx
        import numpy as np
    except ImportError as e:
        print(f"[inspect] Missing dependency: {e}. Install with: pip install matplotlib networkx")
        return

    if not org.malfunctions:
        print("[inspect] plot_disease_comparison: no malfunctions found; falling back to plot_organism.")
        plot_organism(org, save_path=save_path, show=show)
        return

    if not org.healthy_baseline:
        print("[inspect] plot_disease_comparison: no healthy_baseline found; falling back to plot_disease_organism.")
        plot_disease_organism(org, save_path=save_path, show=show)
        return

    from .dynamics import compute_phenotypes

    disease_phenos = compute_phenotypes(org, org.baseline_state,  noise=False)
    healthy_phenos = compute_phenotypes(org, org.healthy_baseline, noise=False)

    # ── Shared data ──────────────────────────────────────────────────────────
    gene_id_to_name = {g.id: g.name for g in org.genes}
    gene_id_to_mod: dict[str, int] = {}
    for k, mod in enumerate(org.modules):
        for gid in mod.gene_ids:
            gene_id_to_mod[gid] = k
    observable_set = set(org.observable_genes)

    # Malfunction targets (gene ids only)
    malfunction_gene_ids = {
        m.target for m in org.malfunctions
        if any(g.id == m.target for g in org.genes)
    }
    # Map gene_id → malfunction type string for labelling
    malfunction_type_by_gene: dict[str, str] = {}
    for m in org.malfunctions:
        if m.target in malfunction_gene_ids:
            malfunction_type_by_gene[m.target] = m.type

    # Genes that shifted significantly (|Δ| > 0.1)
    shifted_gene_ids = {
        g.id for g in org.genes
        if abs(org.baseline_state.get(g.id, 0.0) - org.healthy_baseline.get(g.id, 0.0)) > 0.1
    }

    # Activity colourmap: blue (0) → dark centre → red (1)
    act_cmap = mcolors.LinearSegmentedColormap.from_list(
        "activity", ["#1565C0", "#1B2631", "#C62828"], N=256
    )

    # ── Figure ───────────────────────────────────────────────────────────────
    BG = "#0d0d1a"
    PANEL_BG = "#111122"

    ct_label = org.cell_type.label if org.cell_type else "unknown cell type"
    malfunction_strs = "; ".join(m.description for m in org.malfunctions)
    max_desc  = 100
    title_desc = (malfunction_strs[:max_desc] + "…") if len(malfunction_strs) > max_desc else malfunction_strs

    HEALTHY_COLOR        = "#888888"
    DISEASE_COLOR_ABERRANT = "#EF5350"
    ph_colors_ok         = ["#80DEEA", "#A5D6A7", "#FFF176", "#FFAB91", "#CE93D8"]

    # ── Figure: 2 rows — GRNs top, bar chart bottom ───────────────────────
    fig = plt.figure(figsize=(26, 16))
    fig.patch.set_facecolor(BG)
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[2.2, 1],
                           hspace=0.12, wspace=0.06)
    ax_left  = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    ax_bar   = fig.add_subplot(gs[1, :])   # spans both columns
    for ax in (ax_left, ax_right, ax_bar):
        ax.set_facecolor(PANEL_BG)

    fig.suptitle(
        f"Healthy vs Disease  ·  {ct_label}  ·  seed={org.seed}",
        color="#EF5350", fontsize=14, fontweight="bold", y=0.99,
    )
    fig.text(0.5, 0.975, title_desc,
             color="#aaa", fontsize=10, ha="center", va="top", style="italic")

    # ── Build shared graph + layout ───────────────────────────────────────
    G = nx.DiGraph()
    for g in org.genes:
        G.add_node(g.id)
    for r in org.relations:
        G.add_edge(r.src, r.dst, weight=r.strength, etype=r.type)

    pos = nx.spring_layout(G, seed=org.seed, k=2.5)
    act_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "activates"]
    inh_edges = [(u, v) for u, v, d in G.edges(data=True) if d["etype"] == "inhibits"]

    def _draw_module_blobs(ax) -> None:
        for k, mod in enumerate(org.modules):
            member_ids = [gid for gid in mod.gene_ids if gid in pos]
            if not member_ids:
                continue
            pts = np.array([pos[gid] for gid in member_ids])
            cx, cy = pts.mean(axis=0)
            rx = (float(np.abs(pts[:, 0] - cx).max()) + 0.18 if len(pts) > 1 else 0.18) * 1.15
            ry = (float(np.abs(pts[:, 1] - cy).max()) + 0.18 if len(pts) > 1 else 0.18) * 1.05
            ax.add_patch(mpatches.Ellipse(
                (cx, cy), width=rx * 2, height=ry * 2,
                facecolor=MODULE_HEX[k % len(MODULE_HEX)],
                edgecolor=MODULE_HEX[k % len(MODULE_HEX)],
                alpha=0.13, linewidth=2.5, linestyle="--", zorder=0,
            ))
            ax.text(cx, cy + ry * 0.82, mod.label,
                    color=MODULE_HEX[k % len(MODULE_HEX)], fontsize=9,
                    ha="center", va="bottom", alpha=0.8, style="italic", zorder=1)

    def _draw_edges(ax) -> None:
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=act_edges,
                               edge_color="#00e676",
                               width=[G[u][v]["weight"] * 2.0 for u, v in act_edges],
                               alpha=0.55, arrows=True, arrowsize=16,
                               connectionstyle="arc3,rad=0.12")
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=inh_edges,
                               edge_color="#ff4444",
                               width=[G[u][v]["weight"] * 2.0 for u, v in inh_edges],
                               alpha=0.55, arrows=True, arrowsize=16, style="dashed",
                               connectionstyle="arc3,rad=0.12")

    def _draw_signals(ax, disease: bool = False) -> None:
        all_positions = np.array(list(pos.values()))
        centroid = all_positions.mean(axis=0)
        for sig in org.signals:
            if sig.targets and sig.targets[0] in pos:
                tp = np.array(pos[sig.targets[0]])
                d  = tp - centroid
                norm = np.linalg.norm(d)
                d = d / norm if norm > 0 else d
                sig_pos = tp + d * 0.38
            else:
                sig_pos = centroid + np.array([0.5, 0.5])
            is_chronic = disease and any(
                m.target == sig.id and m.type == "PERSIST" for m in org.malfunctions
            )
            sc = "#EF5350" if is_chronic else "#FFD54F"
            ax.scatter(*sig_pos, s=400, marker="D", color=sc, alpha=0.9,
                       edgecolors="white", linewidths=1.2, zorder=5)
            prefix = "⚡ " if is_chronic else ""
            # Signal labels in italic + smaller so they don't compete with gene labels
            ax.text(sig_pos[0], sig_pos[1] + 0.09, f"{prefix}{sig.label}",
                    color=sc, fontsize=8, ha="center", va="bottom",
                    style="italic", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="#0d0d1a",
                              edgecolor="none", alpha=0.6))
            edge_color = "#00e676" if sig.mode == "activates" else "#ff4444"
            for tgt in sig.targets:
                if tgt in pos:
                    ax.annotate("", xy=np.array(pos[tgt]), xytext=sig_pos,
                                arrowprops=dict(arrowstyle="->", color=edge_color,
                                                lw=1.5, alpha=0.7,
                                                connectionstyle="arc3,rad=0.15"),
                                zorder=4)

    def _draw_nodes(ax, states: dict, highlight: bool = False) -> None:
        node_colors, node_sizes, edge_colors, edge_widths = [], [], [], []
        for g in org.genes:
            act = states.get(g.id, 0.0)
            is_malf = highlight and (g.id in malfunction_gene_ids)
            if is_malf:
                # Magenta fill — outside the activity colormap, impossible to miss
                node_colors.append("#E040FB")
                node_sizes.append(1100)
                edge_colors.append("white")
                edge_widths.append(5.0)
            else:
                node_colors.append(act_cmap(act))
                node_sizes.append(600 if g.id in observable_set else 360)
                edge_colors.append("white" if g.id in observable_set else "#555")
                edge_widths.append(2.0 if g.id in observable_set else 1.0)

        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                               node_size=node_sizes, alpha=0.93,
                               linewidths=edge_widths, edgecolors=edge_colors)
        # Gene labels: bold white, larger font, with dark halo for contrast
        for gid, gname in gene_id_to_name.items():
            if gid not in pos:
                continue
            x, y = pos[gid]
            # Dark backing text for contrast
            ax.text(x, y, gname, fontsize=10, ha="center", va="center",
                    fontweight="bold", color="white", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#0d0d1a",
                              edgecolor="none", alpha=0.45))

        if highlight:
            # Outer ring around malfunction nodes
            for gid in malfunction_gene_ids:
                if gid in pos:
                    nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=[gid],
                                           node_color="none", node_size=1700,
                                           linewidths=3.5, edgecolors="#E040FB",
                                           alpha=0.6)
            for gid, mtype in malfunction_type_by_gene.items():
                if gid not in pos:
                    continue
                x, y = pos[gid]
                ax.text(x, y + 0.17, f"⚠ {mtype}",
                        color="white", fontsize=10, ha="center", va="bottom",
                        fontweight="bold", zorder=12,
                        bbox=dict(boxstyle="round,pad=0.25", facecolor="#7f1500",
                                  edgecolor="#EF5350", linewidth=1.5, alpha=0.95))
            for g in org.genes:
                if g.id in shifted_gene_ids and g.id in pos:
                    x, y = pos[g.id]
                    ax.text(x + 0.11, y + 0.11, "★",
                            color="#FFC107", fontsize=12, ha="center", va="center",
                            fontweight="bold", zorder=11,
                            bbox=dict(boxstyle="round,pad=0.05", facecolor="#0d0d1a",
                                      edgecolor="none", alpha=0.7))

    # ── Left: HEALTHY ─────────────────────────────────────────────────────
    _draw_module_blobs(ax_left)
    _draw_edges(ax_left)
    _draw_nodes(ax_left, org.healthy_baseline, highlight=False)
    _draw_signals(ax_left, disease=False)
    ax_left.set_title(f"Healthy  ·  {ct_label}", color="#4CAF50", fontsize=13, pad=12)
    ax_left.axis("off")

    # ── Right: DISEASE ────────────────────────────────────────────────────
    _draw_module_blobs(ax_right)
    _draw_edges(ax_right)
    _draw_nodes(ax_right, org.baseline_state, highlight=True)
    _draw_signals(ax_right, disease=True)
    ax_right.set_title(f"Disease  ·  {ct_label}", color="#EF5350", fontsize=13, pad=12)
    ax_right.axis("off")

    # ── Shared colorbar (right of disease panel) ──────────────────────────
    sm = plt.cm.ScalarMappable(cmap=act_cmap, norm=mcolors.Normalize(vmin=0, vmax=1))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax_right, location="right", shrink=0.55, pad=0.02, aspect=28)
    cb.set_label("Node activity (0–1)", color="#aaa", fontsize=9)
    cb.ax.yaxis.set_tick_params(color="#aaa", labelsize=8)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color="#aaa")
    cb.outline.set_edgecolor("#444")

    # ── GRN legend ────────────────────────────────────────────────────────
    grn_legend = [
        mpatches.Patch(color="#00e676", label="→ activates"),
        mpatches.Patch(color="#ff4444", label="⇢ inhibits (dashed)"),
        mpatches.Patch(color="#FFD54F", label="◆ signal input"),
        mpatches.Patch(color="#EF5350", label="◆ chronic signal (PERSIST)"),
        mpatches.Patch(facecolor="#E040FB", edgecolor="white", linewidth=2,
                       label="⚠ malfunction gene (magenta)"),
        mpatches.Patch(facecolor="#333", edgecolor="white", linewidth=2,
                       label="○ observable gene (white border)"),
        mpatches.Patch(color="#FFC107", label="★ shifted |Δ| > 0.1"),
    ]
    ax_left.legend(handles=grn_legend, loc="lower left", ncol=2, fontsize=8.5,
                   facecolor="#1a1a2e", edgecolor="#555", labelcolor="white",
                   framealpha=0.9)

    # ── Bottom: vertical bar chart (genes + phenotypes on x-axis) ─────────
    gene_names        = [g.name for g in org.genes]
    healthy_gene_vals = [org.healthy_baseline.get(g.id, 0.0) for g in org.genes]
    disease_gene_vals = [org.baseline_state.get(g.id,  0.0) for g in org.genes]
    bar_colors        = [MODULE_HEX[gene_id_to_mod.get(g.id, 0) % len(MODULE_HEX)]
                         for g in org.genes]

    ph_labels       = [ph.label for ph in org.phenotypes]
    ph_healthy_vals = [healthy_phenos.get(ph.label, 0.5) for ph in org.phenotypes]
    ph_disease_vals = [disease_phenos.get(ph.label, 0.5) for ph in org.phenotypes]

    n_genes  = len(org.genes)
    n_phenos = len(org.phenotypes)
    gap      = 1.0   # space between gene groups
    bw       = 0.35  # bar width

    # Gene groups
    gene_xs = np.arange(n_genes) * gap
    ax_bar.bar(gene_xs - bw/2, healthy_gene_vals, width=bw, color=HEALTHY_COLOR,
               alpha=0.55, zorder=2, label="healthy")
    ax_bar.bar(gene_xs + bw/2, disease_gene_vals, width=bw, color=bar_colors,
               alpha=0.85, zorder=2, label="disease")
    for i, g in enumerate(org.genes):
        if g.id in malfunction_gene_ids:
            ax_bar.axvspan(gene_xs[i] - gap*0.45, gene_xs[i] + gap*0.45,
                           color="#E040FB", alpha=0.08, zorder=0)
            ax_bar.text(gene_xs[i], max(healthy_gene_vals[i], disease_gene_vals[i]) + 0.04,
                        f"⚠ {malfunction_type_by_gene[g.id]}",
                        color="#E040FB", fontsize=8, ha="center", va="bottom",
                        fontweight="bold")
        if g.id in observable_set:
            ax_bar.text(gene_xs[i], -0.07, "👁", fontsize=8, ha="center", va="top",
                        color="#aaa")

    # Separator
    sep_x = gene_xs[-1] + gap * 0.7
    ax_bar.axvline(sep_x, color="#444", linewidth=1.5, linestyle="--")
    ax_bar.text(sep_x + 0.1, 0.95, "phenotypes →", color="#888", fontsize=9,
                va="top", style="italic")

    # Phenotype groups
    ph_xs = sep_x + gap * 1.0 + np.arange(n_phenos) * gap * 1.3
    for i, ph in enumerate(org.phenotypes):
        lo, hi = org.healthy_phenotype_ranges.get(ph.label, (0.0, 1.0))
        is_aberrant = not (lo <= ph_disease_vals[i] <= hi)
        dis_color = DISEASE_COLOR_ABERRANT if is_aberrant else ph_colors_ok[i % len(ph_colors_ok)]
        ax_bar.bar(ph_xs[i] - bw/2, ph_healthy_vals[i], width=bw,
                   color=HEALTHY_COLOR, alpha=0.55, zorder=2)
        ax_bar.bar(ph_xs[i] + bw/2, ph_disease_vals[i], width=bw,
                   color=dis_color, alpha=0.85, zorder=2)
        # Healthy range band
        ax_bar.fill_between([ph_xs[i] - gap*0.45, ph_xs[i] + gap*0.45],
                            lo, hi, color="#ffffff", alpha=0.05, zorder=0)
        ax_bar.text(ph_xs[i] - gap*0.42, lo, f"{lo:.2f}", color="#666",
                    fontsize=7.5, va="bottom")
        ax_bar.text(ph_xs[i] - gap*0.42, hi, f"{hi:.2f}", color="#666",
                    fontsize=7.5, va="top")
        val_y = ph_disease_vals[i] + 0.03
        ax_bar.text(ph_xs[i] + bw/2, val_y, f"{ph_disease_vals[i]:.2f}",
                    color=dis_color, fontsize=8, ha="center", va="bottom", fontweight="bold")
        if is_aberrant:
            ax_bar.text(ph_xs[i], -0.07, "✕", color=DISEASE_COLOR_ABERRANT,
                        fontsize=11, ha="center", va="top", fontweight="bold")

    all_xs = np.concatenate([gene_xs, ph_xs])
    all_labels = gene_names + ph_labels
    ax_bar.set_xticks(all_xs)
    ax_bar.set_xticklabels(all_labels, fontsize=10, color="white", rotation=35,
                            ha="right")
    ax_bar.set_ylim(-0.12, 1.15)
    ax_bar.set_ylabel("Activity (0–1)", color="#aaa", fontsize=10)
    ax_bar.axhline(0.5, color="#ffffff18", linewidth=1, linestyle="--", zorder=1)
    ax_bar.set_title("Gene activity & phenotype readouts — healthy vs disease",
                     color="white", fontsize=11, pad=8)
    ax_bar.tick_params(colors="white", axis="both")
    for sp in ("top", "right"):
        ax_bar.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax_bar.spines[sp].set_edgecolor("#444")

    bar_legend = [
        mpatches.Patch(color=HEALTHY_COLOR, alpha=0.6, label="healthy"),
        mpatches.Patch(color="#aaa", label="disease (in range)"),
        mpatches.Patch(color=DISEASE_COLOR_ABERRANT, label="disease (aberrant ✕)"),
    ]
    ax_bar.legend(handles=bar_legend, loc="upper right", fontsize=9,
                  facecolor="#1a1a2e", edgecolor="#555", labelcolor="white",
                  framealpha=0.9)

    fig.subplots_adjust(left=0.04, right=0.97, top=0.96, bottom=0.1)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
        print(f"[inspect] Saved → {save_path}")
    if show:
        plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# Session replay — agent reasoning visualiser
# ---------------------------------------------------------------------------

def plot_session(
    session: "ExperimentSession",
    save_path: str | None = None,
    show: bool = True,
    observable_only: bool = True,
    agent_log: dict | None = None,
) -> None:
    """
    Visualise a completed ExperimentSession as a heatmap "movie".

    Layout (top → bottom):
      - Turn strip           : agent turn number per column (if agent_log provided)
      - Intervention strip   : what was perturbed in each column
      - Gene state heatmap   : activity per gene per experiment
      - Phenotype heatmap    : phenotype values per experiment
          · disease mode: aberrant cells outlined in red

    Columns: baseline (col 0) then each run_experiment call in order.
    Rows: observable genes (+ any directly intervened genes) + phenotypes.

    agent_log: optional dict loaded from a run_agent() log file; adds turn-number
               labels and reasoning snippets to the intervention strip.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import matplotlib.colors as mcolors
        import numpy as np
    except ImportError as e:
        print(f"[inspect] Missing dependency: {e}. Install with: pip install matplotlib")
        return

    from .dynamics import compute_phenotypes

    org     = session.organism
    log     = session._experiment_log
    is_dis  = session._is_disease

    # ── Which genes to show ─────────────────────────────────────────────────
    name_to_id = {g.name: g.id for g in org.genes}
    intervened_ids: set[str] = set()
    for entry in log:
        for k in entry["interventions"]:
            if k in name_to_id:
                intervened_ids.add(name_to_id[k])

    if observable_only:
        obs_set = set(org.observable_genes)
        show_gene_ids = [g.id for g in org.genes if g.id in obs_set or g.id in intervened_ids]
    else:
        show_gene_ids = [g.id for g in org.genes]

    gene_id_to_name = {g.id: g.name for g in org.genes}
    gene_id_to_mod  = {gid: k for k, m in enumerate(org.modules) for gid in m.gene_ids}
    ph_labels = [p.label for p in org.phenotypes]
    n_genes   = len(show_gene_ids)
    n_phenos  = len(ph_labels)

    # ── Build data matrices ─────────────────────────────────────────────────
    # Start with healthy baseline (col 0); for disease add disease-start (col 1)
    baseline_state  = org.healthy_baseline if (is_dis and org.healthy_baseline) else org.baseline_state
    baseline_phenos = compute_phenotypes(org, baseline_state, noise=False)

    cols_gene:  list[dict] = [baseline_state]
    cols_pheno: list[dict] = [baseline_phenos]
    col_labels: list[str]  = ["healthy\nbaseline" if is_dis else "baseline"]
    col_types:  list[str]  = ["baseline"]   # "baseline" | "disease" | "experiment"

    if is_dis and org.healthy_baseline:
        dis_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
        cols_gene.append(org.baseline_state)
        cols_pheno.append(dis_phenos)
        col_labels.append("disease\nstart")
        col_types.append("disease")

    for entry in log:
        cols_gene.append(entry.get("gene_state", {}))
        cols_pheno.append(entry.get("phenotypes", {}))
        ivs = entry["interventions"]
        parts = []
        IV_SYM = {"BLOCK": "✕", "BOOST": "▲", "DAMPEN": "▼"}
        for name, val in ivs.items():
            itype = val.get("type", "?") if isinstance(val, dict) else str(val)
            parts.append(f"{IV_SYM.get(itype, '?')}{name}")
        col_labels.append("\n".join(parts) if parts else "—")
        col_types.append("experiment")

    n_cols = len(cols_gene)

    gene_mat  = np.zeros((n_genes, n_cols))
    pheno_mat = np.zeros((n_phenos, n_cols))
    for ci, (gs, ph) in enumerate(zip(cols_gene, cols_pheno)):
        for ri, gid in enumerate(show_gene_ids):
            gene_mat[ri, ci] = gs.get(gid, 0.0)
        for ri, lbl in enumerate(ph_labels):
            pheno_mat[ri, ci] = ph.get(lbl, 0.0)

    # ── Intervention target lookup ──────────────────────────────────────────
    IV_COLOR = {"BLOCK": "#EF5350", "BOOST": "#66BB6A", "DAMPEN": "#FFA726"}
    # col_iv_markers[ci] = list of (gene_row_index, color, symbol)
    exp_col_offset = col_types.index("experiment") if "experiment" in col_types else 1
    col_iv_markers: list[list] = [[] for _ in range(n_cols)]
    for ci, entry in enumerate(log, start=exp_col_offset):
        for name, val in entry["interventions"].items():
            gid = name_to_id.get(name)
            if gid and gid in show_gene_ids:
                itype = val.get("type", "") if isinstance(val, dict) else ""
                col_iv_markers[ci].append((
                    show_gene_ids.index(gid),
                    IV_COLOR.get(itype, "#fff"),
                    {"BLOCK": "✕", "BOOST": "▲", "DAMPEN": "▼"}.get(itype, "?"),
                ))

    # ── Turn attribution from agent log ──────────────────────────────────────
    # Map experiment column index → (turn_number, reasoning_snippet)
    col_turn: dict[int, int] = {}
    col_reasoning: dict[int, str] = {}
    if agent_log:
        # Experiments are numbered by budget_remaining in results.
        # Walk turns and match run_experiment calls to experiment_log order.
        exp_col_start = col_types.index("experiment") if "experiment" in col_types else 1
        exp_order = 0  # counts run_experiment calls seen so far
        for t in agent_log.get("turns", []):
            turn_num = t.get("turn", 0)
            snippet = (t.get("agent_text") or "").strip()
            snippet = snippet[:80].replace("\n", " ")
            for tc in t.get("tool_calls", []):
                if tc["tool"] == "run_experiment":
                    ci = exp_col_start + exp_order
                    col_turn[ci] = turn_num
                    if snippet:
                        col_reasoning[ci] = snippet
                    exp_order += 1

    # ── Figure layout ────────────────────────────────────────────────────────
    BG = "#0d0d1a"; PANEL_BG = "#111122"
    has_turns = bool(col_turn)
    turn_h  = 0.45 if has_turns else 0.0
    strip_h = 1.3
    gene_h  = n_genes * 0.52
    pheno_h = n_phenos * 0.7
    fig_h   = turn_h + strip_h + gene_h + pheno_h + 1.4
    fig_w   = max(14, n_cols * 0.9 + 3.5)

    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG)
    n_rows     = 4 if has_turns else 3
    hr         = ([turn_h, strip_h, gene_h, pheno_h + 0.7] if has_turns
                  else [strip_h, gene_h, pheno_h + 0.7])
    gs_layout  = fig.add_gridspec(
        n_rows, 1, height_ratios=hr,
        hspace=0.04, left=0.13, right=0.96, top=0.93, bottom=0.05,
    )
    row_idx = 0
    if has_turns:
        ax_turns = fig.add_subplot(gs_layout[row_idx]); row_idx += 1
    else:
        ax_turns = None
    ax_strip = fig.add_subplot(gs_layout[row_idx]); row_idx += 1
    ax_gene  = fig.add_subplot(gs_layout[row_idx]); row_idx += 1
    ax_pheno = fig.add_subplot(gs_layout[row_idx])
    active_axes = [ax for ax in (ax_turns, ax_strip, ax_gene, ax_pheno) if ax is not None]
    for ax in active_axes:
        ax.set_facecolor(PANEL_BG)

    title = f"Session Replay  ·  {org.id}  ·  {len(log)} experiments"
    if is_dis and org.cell_type:
        title += f"  ·  {org.cell_type.label}"
        if org.malfunctions:
            title += f"\n{org.malfunctions[0].description}"
    fig.suptitle(title, color="#FFC107", fontsize=10, fontweight="bold", y=0.99)

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "activity", ["#1565C0", "#1B2631", "#C62828"], N=256)

    # ── Turn attribution strip ───────────────────────────────────────────────
    if ax_turns is not None:
        ax_turns.set_xlim(0, n_cols); ax_turns.set_ylim(0, 1); ax_turns.axis("off")
        for ci in range(n_cols):
            tn = col_turn.get(ci)
            if tn is not None:
                snip = col_reasoning.get(ci, "")
                label = f"T{tn}"
                ax_turns.text(ci + 0.5, 0.62, label, color="#FFC107",
                              fontsize=6, ha="center", va="center", fontweight="bold")
                if snip:
                    ax_turns.text(ci + 0.5, 0.2, snip[:18],
                                  color="#666", fontsize=4.5, ha="center", va="center")
        ax_turns.set_title("Agent turns", color="#555", fontsize=6, pad=1, loc="left")

    # ── Strip panel ─────────────────────────────────────────────────────────
    ax_strip.set_xlim(0, n_cols); ax_strip.set_ylim(0, 1); ax_strip.axis("off")
    stripe_colors = {"baseline": "#1a2a1a", "disease": "#2a1a1a", "experiment": "#16213e"}
    border_colors = {"baseline": "#4CAF50",  "disease": "#EF5350",  "experiment": "#334"}
    for ci, (lbl, ctype) in enumerate(zip(col_labels, col_types)):
        ax_strip.add_patch(mpatches.FancyBboxPatch(
            (ci + 0.05, 0.04), 0.9, 0.92,
            boxstyle="round,pad=0.01",
            facecolor=stripe_colors[ctype],
            edgecolor=border_colors[ctype], linewidth=1.4, zorder=0,
        ))
        txt_col = {"baseline": "#4CAF50", "disease": "#EF5350", "experiment": "#ccc"}[ctype]
        if col_iv_markers[ci]:
            txt_col = col_iv_markers[ci][0][1]
        ax_strip.text(ci + 0.5, 0.54, lbl, color=txt_col, fontsize=6.8,
                      ha="center", va="center", fontweight="bold", multialignment="center")
        ax_strip.text(ci + 0.5, 0.1, str(ci), color="#555", fontsize=5.5, ha="center", va="bottom")

    # ── Gene heatmap ────────────────────────────────────────────────────────
    ax_gene.imshow(gene_mat, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                   extent=[0, n_cols, -0.5, n_genes - 0.5], origin="upper", zorder=1)

    for ci, markers in enumerate(col_iv_markers):
        for row_i, color, sym in markers:
            draw_y = n_genes - row_i - 1.5
            ax_gene.add_patch(mpatches.Rectangle(
                (ci, draw_y), 1, 1,
                lw=2, edgecolor=color, facecolor="none", zorder=3))
            ax_gene.text(ci + 0.12, draw_y + 0.52, sym,
                         color=color, fontsize=7, va="center", fontweight="bold", zorder=4)

    for ci in range(1, n_cols):
        lw = 1.8 if col_types[ci] in ("disease",) else 0.35
        ec = "#EF5350" if col_types[ci] == "disease" else "#2a2a3a"
        ax_gene.axvline(ci, color=ec, linewidth=lw, zorder=2)

    ax_gene.set_yticks(range(n_genes))
    ax_gene.set_yticklabels([gene_id_to_name[gid] for gid in reversed(show_gene_ids)],
                             fontsize=7.5)
    for tick, gid in zip(ax_gene.get_yticklabels(), reversed(show_gene_ids)):
        tick.set_color(MODULE_HEX[gene_id_to_mod.get(gid, 0) % len(MODULE_HEX)])
    ax_gene.set_xticks([]); ax_gene.set_xlim(0, n_cols)
    ax_gene.set_title("Gene activity  (rows = genes, columns = experiments)",
                      color="#777", fontsize=7.5, pad=3, loc="left")
    for sp in ax_gene.spines.values(): sp.set_edgecolor("#2a2a3a")

    # ── Phenotype heatmap ───────────────────────────────────────────────────
    im_ph = ax_pheno.imshow(pheno_mat, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                            extent=[0, n_cols, -0.5, n_phenos - 0.5], origin="upper", zorder=1)

    for ci in range(1, n_cols):
        lw = 1.8 if col_types[ci] == "disease" else 0.35
        ec = "#EF5350" if col_types[ci] == "disease" else "#2a2a3a"
        ax_pheno.axvline(ci, color=ec, linewidth=lw, zorder=2)

    if is_dis and org.healthy_phenotype_ranges:
        for ri, ph in enumerate(org.phenotypes):
            lo, hi = org.healthy_phenotype_ranges.get(ph.label, (0.0, 1.0))
            for ci in range(n_cols):
                val = pheno_mat[n_phenos - 1 - ri, ci]
                if not (lo <= val <= hi):
                    ax_pheno.add_patch(mpatches.Rectangle(
                        (ci, ri - 0.5), 1, 1,
                        lw=2, edgecolor="#EF5350", facecolor="none", zorder=3))

    for ri in range(n_phenos):
        for ci in range(n_cols):
            val = pheno_mat[n_phenos - 1 - ri, ci]
            tc = "white" if 0.2 < val < 0.78 else ("#ddd" if val <= 0.2 else "#111")
            ax_pheno.text(ci + 0.5, ri, f"{val:.2f}",
                          color=tc, fontsize=6.5, ha="center", va="center", zorder=4)

    ax_pheno.set_yticks(range(n_phenos))
    ax_pheno.set_yticklabels(list(reversed(ph_labels)), fontsize=8, color="#CE93D8")
    ax_pheno.set_xticks([ci + 0.5 for ci in range(n_cols)])
    ax_pheno.set_xticklabels([str(i) for i in range(n_cols)], fontsize=6.5, color="#555")
    ax_pheno.set_xlim(0, n_cols)
    ax_pheno.set_xlabel("Experiment index  (0 = baseline)", color="#555", fontsize=8)
    ax_pheno.set_title("Phenotype values  (red outline = outside healthy range)",
                       color="#777", fontsize=7.5, pad=3, loc="left")
    ax_pheno.tick_params(left=False, bottom=False)
    for sp in ax_pheno.spines.values(): sp.set_edgecolor("#2a2a3a")

    # ── Colorbar + legend ───────────────────────────────────────────────────
    cbar_ax = fig.add_axes([0.97, 0.08, 0.012, 0.5])
    cb = fig.colorbar(im_ph, cax=cbar_ax)
    cb.set_label("Activity", color="#aaa", fontsize=7)
    cb.ax.yaxis.set_tick_params(color="#aaa", labelsize=6)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color="#aaa")
    cb.outline.set_edgecolor("#333")

    legend_handles = [
        mpatches.Patch(color="#EF5350", label="✕ BLOCK — suppress to zero"),
        mpatches.Patch(color="#66BB6A", label="▲ BOOST — saturate to max"),
        mpatches.Patch(color="#FFA726", label="▼ DAMPEN — reduce to low"),
    ]
    if is_dis:
        legend_handles.append(
            mpatches.Patch(facecolor="none", edgecolor="#EF5350", linewidth=2,
                           label="aberrant phenotype"))
    ax_strip.legend(handles=legend_handles, loc="upper right", fontsize=7,
                    facecolor="#1a1a2e", edgecolor="#555", labelcolor="white",
                    framealpha=0.9, bbox_to_anchor=(1.0, 1.02))

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
        print(f"[inspect] Saved → {save_path}")
    if show:
        plt.show()
    plt.close()
