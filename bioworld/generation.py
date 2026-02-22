"""Procedural organism generation for BioWorld."""
from __future__ import annotations

import math
import random
import uuid
from typing import Any

import numpy as np

from .schema import (
    DynamicsConfig,
    Gene,
    Module,
    Organism,
    Phenotype,
    PhenotypeReadout,
    Relation,
    Signal,
)
from .vocabulary import MODULE_LABELS, PHENOTYPE_LABELS, SIGNAL_LABELS


def generate_organism(
    n_genes: int = 20,
    n_modules: int = 4,
    n_signals: int = 3,
    n_phenotypes: int = 3,
    observability: float = 0.6,
    intra_module_density: float = 0.4,
    inter_module_density: float = 0.08,
    inhibition_fraction: float = 0.3,
    n_ffls: int = 2,
    n_feedback: int = 2,
    noise_sigma: float = 0.01,
    seed: int | None = None,
) -> Organism:
    """Generate a synthetic organism with gene regulatory network."""
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    rng_py = random.Random(seed)
    rng_np = np.random.default_rng(seed)

    organism_id = f"org_{seed:08x}"

    # 1. Sample gene names
    genes = [
        Gene(id=f"g_{i:03d}", name=f"G{i:03d}")
        for i in range(1, n_genes + 1)
    ]
    gene_ids = [g.id for g in genes]

    # 2. Assign genes to modules (planted partition)
    module_labels = rng_py.sample(MODULE_LABELS, min(n_modules, len(MODULE_LABELS)))
    module_assignments: dict[str, int] = {}  # gene_id -> module_index
    # Distribute genes evenly
    for i, gid in enumerate(gene_ids):
        module_assignments[gid] = i % n_modules

    modules = [
        Module(
            id=f"m_{k:02d}",
            label=module_labels[k],
            gene_ids=[gid for gid, m in module_assignments.items() if m == k],
        )
        for k in range(n_modules)
    ]

    # 3. Build signed weighted adjacency
    W: dict[str, dict[str, float]] = {gid: {} for gid in gene_ids}  # W[dst][src] = weight
    relations: list[Relation] = []

    for i, dst in enumerate(gene_ids):
        for j, src in enumerate(gene_ids):
            if src == dst:
                continue
            same_module = module_assignments[src] == module_assignments[dst]
            p = intra_module_density if same_module else inter_module_density
            if rng_np.random() < p:
                strength = float(rng_np.uniform(0.5, 1.5))
                is_inhibitor = rng_np.random() < inhibition_fraction
                sign = -1.0 if is_inhibitor else 1.0
                W[dst][src] = sign * strength
                relations.append(
                    Relation(
                        src=src,
                        dst=dst,
                        type="inhibits" if is_inhibitor else "activates",
                        strength=strength,
                    )
                )

    # 4. Inject FFLs (coherent: A→B, A→C, B→C, all activating)
    for _ in range(n_ffls):
        candidates = gene_ids[:]
        if len(candidates) < 3:
            break
        rng_py.shuffle(candidates)
        a, b, c = candidates[:3]
        for src, dst in [(a, b), (a, c), (b, c)]:
            strength = float(rng_np.uniform(0.6, 1.2))
            if dst not in W:
                W[dst] = {}
            W[dst][src] = strength
            # Update or add relation
            existing = next((r for r in relations if r.src == src and r.dst == dst), None)
            if existing is None:
                relations.append(Relation(src=src, dst=dst, type="activates", strength=strength))
            else:
                existing.type = "activates"
                existing.strength = strength

    # 5. Inject feedback edges (positive feedback: mutual activation)
    for _ in range(n_feedback):
        if len(gene_ids) < 2:
            break
        a, b = rng_py.sample(gene_ids, 2)
        for src, dst in [(a, b), (b, a)]:
            strength = float(rng_np.uniform(0.4, 0.9))
            W[dst][src] = strength
            existing = next((r for r in relations if r.src == src and r.dst == dst), None)
            if existing is None:
                relations.append(Relation(src=src, dst=dst, type="activates", strength=strength))

    # 6. Assign signals
    signal_label_pool = rng_py.sample(SIGNAL_LABELS, min(n_signals, len(SIGNAL_LABELS)))
    signals: list[Signal] = []
    for k in range(n_signals):
        n_targets = rng_py.randint(1, min(3, n_genes))
        targets = rng_py.sample(gene_ids, n_targets)
        mode = rng_py.choice(["activates", "inhibits"])
        strength = float(rng_np.uniform(0.3, 0.8))
        signals.append(
            Signal(
                id=f"s_{k:02d}",
                label=signal_label_pool[k],
                targets=targets,
                mode=mode,
                strength=strength,
            )
        )

    # 7. Sample bias per gene
    biases = rng_np.uniform(-0.5, 0.5, size=n_genes)
    bias_map = {gid: float(biases[i]) for i, gid in enumerate(gene_ids)}

    # 8. Build dynamics rule
    rule: dict[str, Any] = {}
    for dst in gene_ids:
        inputs = [
            {"src": src, "weight": float(W[dst][src])}
            for src in W[dst]
        ]
        rule[dst] = {"bias": bias_map[dst], "inputs": inputs}

    dynamics = DynamicsConfig(
        type="continuous_sigmoid",
        dt=1.0,
        noise_sigma=noise_sigma,
        rule=rule,
    )

    # Temporary organism for baseline simulation
    org_tmp = Organism(
        id=organism_id,
        genes=genes,
        modules=modules,
        signals=signals,
        relations=relations,
        phenotypes=[],  # filled below
        dynamics=dynamics,
        seed=seed,
        baseline_state={},
        observable_genes=[],
    )

    # Simulate baseline (no interventions, no active signals)
    from .dynamics import simulate_sigmoid
    result = simulate_sigmoid(org_tmp, interventions={}, active_signals={}, rng=rng_np)
    baseline_state = result["final_state"]

    # 9. Create phenotype readouts
    phenotype_label_pool = rng_py.sample(PHENOTYPE_LABELS, min(n_phenotypes, len(PHENOTYPE_LABELS)))
    phenotypes: list[Phenotype] = []
    for k in range(n_phenotypes):
        n_deps = rng_py.randint(2, min(4, n_genes))
        dep_genes = rng_py.sample(gene_ids, n_deps)
        weights = [float(rng_np.uniform(-1.5, 1.5)) for _ in dep_genes]
        ph_bias = float(rng_np.uniform(-0.5, 0.5))
        phenotypes.append(
            Phenotype(
                id=f"p_{k:02d}",
                label=phenotype_label_pool[k],
                readout=PhenotypeReadout(
                    type="sigmoid_weighted_sum",
                    depends_on=dep_genes,
                    weights=weights,
                    bias=ph_bias,
                ),
            )
        )

    # 10. Select observable genes covering all modules
    n_observable = max(n_modules, math.ceil(observability * n_genes))
    observable_set: set[str] = set()
    # Ensure at least one gene per module
    for mod in modules:
        if mod.gene_ids:
            observable_set.add(rng_py.choice(mod.gene_ids))
    # Fill up to n_observable
    remaining = [gid for gid in gene_ids if gid not in observable_set]
    rng_py.shuffle(remaining)
    for gid in remaining:
        if len(observable_set) >= n_observable:
            break
        observable_set.add(gid)
    observable_genes = list(observable_set)

    return Organism(
        id=organism_id,
        genes=genes,
        modules=modules,
        signals=signals,
        relations=relations,
        phenotypes=phenotypes,
        dynamics=dynamics,
        seed=seed,
        baseline_state=baseline_state,
        observable_genes=observable_genes,
    )
