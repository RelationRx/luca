"""Procedural organism generation for Lemonoids."""
from __future__ import annotations

import math
import random
import uuid
from typing import Any

import numpy as np

from .schema import (
    CellType,
    DynamicsConfig,
    Gene,
    Malfunction,
    Module,
    Organism,
    Phenotype,
    PhenotypeReadout,
    Relation,
    Signal,
)
from .vocabulary import (
    CELL_TYPE_DESCRIPTIONS,
    CELL_TYPE_LABELS,
    MALFUNCTION_TYPES,
    MODULE_LABELS,
    PHENOTYPE_LABELS,
    SIGNAL_LABELS,
)


DIFFICULTY_PRESETS: dict[str, dict] = {
    # Easy / "prokaryote-like": near-linear dynamics, no feedback loops,
    # high observability, minimal noise.
    "easy": dict(
        observability=0.8,
        intra_module_density=0.25,
        inter_module_density=0.04,
        inhibition_fraction=0.2,
        n_ffls=1,
        n_feedback=0,
        noise_sigma=0.005,
        sigmoid_steepness=0.7,
        latent_fraction=0.0,
    ),
    # Medium / "simple eukaryote": nonlinear dynamics, moderate feedback,
    # moderate observability, no latent genes. Default tier.
    "medium": dict(
        observability=0.6,
        intra_module_density=0.4,
        inter_module_density=0.08,
        inhibition_fraction=0.3,
        n_ffls=2,
        n_feedback=2,
        noise_sigma=0.01,
        sigmoid_steepness=1.0,
        latent_fraction=0.0,
    ),
    # Hard / "complex eukaryote": sharp nonlinear dynamics, dense feedback,
    # long-range inter-module edges, latent confounders, higher noise.
    "hard": dict(
        observability=0.5,
        intra_module_density=0.5,
        inter_module_density=0.15,
        inhibition_fraction=0.4,
        n_ffls=3,
        n_feedback=4,
        noise_sigma=0.03,
        sigmoid_steepness=2.0,
        latent_fraction=0.25,
    ),
}

# Biological metaphor aliases — accepted everywhere difficulty= is used
DIFFICULTY_PRESETS["prokaryote"] = DIFFICULTY_PRESETS["easy"]
DIFFICULTY_PRESETS["simple_eukaryote"] = DIFFICULTY_PRESETS["medium"]
DIFFICULTY_PRESETS["complex_eukaryote"] = DIFFICULTY_PRESETS["hard"]


def generate_organism(
    n_genes: int = 20,
    n_modules: int = 4,
    n_signals: int = 3,
    n_phenotypes: int = 3,
    difficulty: str = "medium",
    observability: float | None = None,
    intra_module_density: float | None = None,
    inter_module_density: float | None = None,
    inhibition_fraction: float | None = None,
    n_ffls: int | None = None,
    n_feedback: int | None = None,
    noise_sigma: float | None = None,
    sigmoid_steepness: float | None = None,
    latent_fraction: float | None = None,
    seed: int | None = None,
) -> Organism:
    """Generate a synthetic organism with gene regulatory network.

    difficulty: "easy" | "medium" | "hard" (default "medium") — sets structural
        and dynamic defaults via DIFFICULTY_PRESETS. Biological metaphor aliases
        are also accepted: "prokaryote", "simple_eukaryote", "complex_eukaryote".
        Individual parameters override preset values.
    """
    # Apply difficulty preset defaults for any unspecified structural parameters
    preset = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS["medium"])
    if observability is None:
        observability = preset["observability"]
    if intra_module_density is None:
        intra_module_density = preset["intra_module_density"]
    if inter_module_density is None:
        inter_module_density = preset["inter_module_density"]
    if inhibition_fraction is None:
        inhibition_fraction = preset["inhibition_fraction"]
    if n_ffls is None:
        n_ffls = preset["n_ffls"]
    if n_feedback is None:
        n_feedback = preset["n_feedback"]
    if noise_sigma is None:
        noise_sigma = preset["noise_sigma"]
    if sigmoid_steepness is None:
        sigmoid_steepness = preset["sigmoid_steepness"]
    if latent_fraction is None:
        latent_fraction = preset["latent_fraction"]
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
        sigmoid_steepness=sigmoid_steepness,
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

    # 11. Select latent genes (hidden + untargetable confounders)
    # Latent genes are drawn from non-observable genes; they influence the network
    # but cannot be seen or targeted by the agent. Malfunction genes (if any) are
    # removed from the latent set afterwards in generate_disease_organism().
    n_latent = round(latent_fraction * n_genes)
    latent_genes: list[str] = []
    if n_latent > 0:
        non_observable = [gid for gid in gene_ids if gid not in observable_set]
        rng_py.shuffle(non_observable)
        latent_genes = non_observable[:n_latent]

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
        difficulty=difficulty,
        latent_genes=latent_genes,
    )


def generate_disease_organism(
    n_malfunctions: int = 1,
    malfunction_types: list[str] | None = None,
    min_phenotype_shift: float = 0.25,
    **organism_kwargs,
) -> Organism:
    """
    Generate a disease organism: a healthy organism with one or more malfunctions
    applied that produce aberrant phenotypes.

    **Detectability guarantee**: every returned organism satisfies both:
      1. At least one phenotype falls outside its healthy range (the disease is observable).
      2. A single corrective intervention exists that restores ≥1 aberrant phenotype:
           LOCK_HI  → BLOCK of the malfunctioning gene
           LOCK_LO  → BOOST of the malfunctioning gene
           PERSIST  → deactivating the persistent signal override

    n_malfunctions: number of malfunctions to apply (1 or 2 recommended)
    malfunction_types: list of types to choose from; None = random from MALFUNCTION_TYPES
    min_phenotype_shift: (unused, kept for API compatibility)
    **organism_kwargs: forwarded to generate_organism() (e.g. seed, n_genes, …)
    """
    from .dynamics import compute_phenotypes, simulate_sigmoid

    # Seed handling: extract seed for cell-type sampling reproducibility
    seed = organism_kwargs.get("seed", None)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
        organism_kwargs["seed"] = seed

    rng_py = random.Random(seed + 9999)  # offset to avoid collision with org rng
    rng_np = np.random.default_rng(seed + 9999)

    # 1. Generate healthy organism
    org = generate_organism(**organism_kwargs)

    # 2. Assign cell type
    ct_index = rng_py.randrange(len(CELL_TYPE_LABELS))
    ct_id = f"ct_{ct_index:02d}"
    cell_type = CellType(
        id=ct_id,
        label=CELL_TYPE_LABELS[ct_index],
        description=CELL_TYPE_DESCRIPTIONS[ct_index],
    )

    # 3. Store healthy baseline
    healthy_baseline = dict(org.baseline_state)

    # 4. Compute healthy phenotype values and ranges
    # Use ±0.15 tolerance — tight enough for perturbations to reliably leave the range
    # while still giving a meaningful "healthy corridor" for the agent to target.
    healthy_phenos = compute_phenotypes(org, healthy_baseline, noise=False)
    healthy_phenotype_ranges: dict[str, tuple[float, float]] = {
        label: (max(0.0, val - 0.15), min(1.0, val + 0.15))
        for label, val in healthy_phenos.items()
    }

    gene_ids = [g.id for g in org.genes]
    signal_ids = [s.id for s in org.signals]
    gene_id_to_name = {g.id: g.name for g in org.genes}
    signal_id_to_label = {s.id: s.label for s in org.signals}

    # Pre-compute which genes appear in any phenotype readout
    phenotype_gene_ids: list[str] = []
    for ph in org.phenotypes:
        phenotype_gene_ids.extend(ph.readout.depends_on)
    phenotype_gene_ids = list(dict.fromkeys(phenotype_gene_ids))  # deduplicated, ordered

    # Pre-compute signal → phenotype relevance (targets overlap with phenotype genes)
    ph_gene_set = set(phenotype_gene_ids)
    relevant_signal_ids = [
        s.id for s in org.signals
        if any(t in ph_gene_set for t in s.targets)
    ]

    allowed_types = malfunction_types if malfunction_types else MALFUNCTION_TYPES

    # Use a very large bias magnitude so the sigmoid saturates regardless of other inputs
    BIAS_SEVERITY = 20.0

    # Pre-scan: find which (gene, mtype) and signal combinations both produce
    # aberrant phenotypes AND are correctable by a single targeted intervention.
    # This provides the guarantee that the malfunction is always in principle
    # discoverable and rescuable by the agent.
    import copy as _pre_copy

    def _probe_gene_malfunction(target_id: str, mtype: str) -> bool:
        """
        Return True iff:
          1. Applying this gene malfunction shifts ≥1 phenotype outside healthy range, AND
          2. The corrective single-gene intervention restores ≥1 of those phenotypes:
               LOCK_HI → BLOCK of target (removes locked-high node)
               LOCK_LO → BOOST of target (restores locked-low node)
        """
        rule = _pre_copy.deepcopy(org.dynamics.rule)
        rule[target_id]["bias"] = BIAS_SEVERITY if mtype == "LOCK_HI" else -BIAS_SEVERITY
        dyn = _pre_copy.deepcopy(org.dynamics)
        dyn.rule = rule
        org_tmp = Organism(
            id=org.id, genes=org.genes, modules=org.modules, signals=org.signals,
            relations=org.relations, phenotypes=org.phenotypes, dynamics=dyn,
            seed=org.seed, baseline_state=healthy_baseline, observable_genes=org.observable_genes,
        )
        # Simulate disease state
        disease_result = simulate_sigmoid(org_tmp, interventions={}, active_signals={},
                                          rng=np.random.default_rng(seed + 1234))
        disease_phenos = compute_phenotypes(org_tmp, disease_result["final_state"], noise=False)
        aberrant = [
            lbl for lbl, v in disease_phenos.items()
            if not (healthy_phenotype_ranges[lbl][0] <= v <= healthy_phenotype_ranges[lbl][1])
        ]
        if not aberrant:
            return False

        # Simulate corrective intervention from disease state
        corrective_iv = {target_id: {"type": "BLOCK"}} if mtype == "LOCK_HI" else {target_id: {"type": "BOOST"}}
        rescue_result = simulate_sigmoid(org_tmp, interventions=corrective_iv, active_signals={},
                                         rng=np.random.default_rng(seed + 5678))
        rescue_phenos = compute_phenotypes(org_tmp, rescue_result["final_state"], noise=False)
        return any(
            healthy_phenotype_ranges[lbl][0] <= rescue_phenos.get(lbl, 0.5) <= healthy_phenotype_ranges[lbl][1]
            for lbl in aberrant
        )

    def _probe_signal_malfunction(sig_id: str, severity: float) -> bool:
        """
        Return True iff:
          1. Chronic activation of this signal shifts ≥1 phenotype outside healthy range, AND
          2. Deactivating the signal (removing the override) restores ≥1 of those phenotypes.
        """
        orig_sig = next(s for s in org.signals if s.id == sig_id)
        new_strength = orig_sig.strength * severity
        overrides = {sig_id: new_strength if orig_sig.mode == "activates" else -new_strength}

        # Simulate disease state
        disease_result = simulate_sigmoid(org, interventions={}, active_signals=overrides,
                                          rng=np.random.default_rng(seed + 1234))
        disease_phenos = compute_phenotypes(org, disease_result["final_state"], noise=False)
        aberrant = [
            lbl for lbl, v in disease_phenos.items()
            if not (healthy_phenotype_ranges[lbl][0] <= v <= healthy_phenotype_ranges[lbl][1])
        ]
        if not aberrant:
            return False

        # Simulate deactivation (signal removed) from disease state
        restore_result = simulate_sigmoid(org, interventions={}, active_signals={},
                                          rng=np.random.default_rng(seed + 5678))
        restore_phenos = compute_phenotypes(org, restore_result["final_state"], noise=False)
        return any(
            healthy_phenotype_ranges[lbl][0] <= restore_phenos.get(lbl, 0.5) <= healthy_phenotype_ranges[lbl][1]
            for lbl in aberrant
        )

    # Build catalogs of malfunctions that are BOTH aberrant AND correctable
    effective_gene_malfunctions: list[tuple[str, str]] = []  # (gene_id, mtype)
    for gid in phenotype_gene_ids:
        for mt in ("LOCK_HI", "LOCK_LO"):
            if mt in allowed_types and _probe_gene_malfunction(gid, mt):
                effective_gene_malfunctions.append((gid, mt))

    effective_signals: list[str] = []
    if "PERSIST" in allowed_types:
        for sid in (relevant_signal_ids or signal_ids):
            if _probe_signal_malfunction(sid, 10.0):
                effective_signals.append(sid)

    def _verify_rescue_combo(
        malfunctions: list[Malfunction],
        org_perturbed: Organism,
        aberrant: list[str],
        chronic_overrides: dict[str, float],
    ) -> bool:
        """
        Return True iff at least one malfunction in the combination has a single
        corrective intervention that restores ≥1 aberrant phenotype to its healthy range:
          LOCK_HI  → BLOCK of the target gene
          LOCK_LO  → BOOST of the target gene
          PERSIST  → simulate without that signal's persistent override
        """
        for m in malfunctions:
            if m.type == "LOCK_HI":
                iv = {m.target: {"type": "BLOCK"}}
                r = simulate_sigmoid(org_perturbed, interventions=iv,
                                     active_signals=chronic_overrides,
                                     rng=np.random.default_rng(seed + 7890))
            elif m.type == "LOCK_LO":
                iv = {m.target: {"type": "BOOST"}}
                r = simulate_sigmoid(org_perturbed, interventions=iv,
                                     active_signals=chronic_overrides,
                                     rng=np.random.default_rng(seed + 7890))
            else:  # PERSIST — remove just this signal's override
                remaining = {k: v for k, v in chronic_overrides.items() if k != m.target}
                r = simulate_sigmoid(org_perturbed, interventions={},
                                     active_signals=remaining,
                                     rng=np.random.default_rng(seed + 7890))

            rescue_phenos = compute_phenotypes(org_perturbed, r["final_state"], noise=False)
            if any(
                healthy_phenotype_ranges[lbl][0] <= rescue_phenos.get(lbl, 0.5) <= healthy_phenotype_ranges[lbl][1]
                for lbl in aberrant
            ):
                return True
        return False

    def _apply_malfunctions(
        n: int,
        max_attempts: int = 10,
    ) -> tuple[list[Malfunction], dict[str, float], any, dict[str, float]]:
        """
        Pick malfunctions that:
          1. cause at least one phenotype to leave its healthy range, AND
          2. admit at least one corrective single-intervention that restores it.
        """
        # If we have pre-confirmed effective malfunctions, use them directly
        gene_pool = effective_gene_malfunctions[:]
        signal_pool = effective_signals[:]
        rng_py.shuffle(gene_pool)
        rng_py.shuffle(signal_pool)

        # Track the last aberrant-but-not-rescuable result as a fallback
        last_aberrant_result: tuple | None = None

        for _attempt in range(max_attempts):
            import copy
            perturbed_rule = copy.deepcopy(org.dynamics.rule)
            chronic_signal_overrides: dict[str, float] = {}
            malfunctions: list[Malfunction] = []

            for _ in range(n):
                # Determine what types are feasible this round
                feasible_types = []
                if gene_pool and any(t in allowed_types for t in ("LOCK_HI", "LOCK_LO")):
                    feasible_types.extend(["LOCK_HI", "LOCK_LO"])
                if signal_pool and "PERSIST" in allowed_types:
                    feasible_types.append("PERSIST")
                if not feasible_types:
                    # Fall back to any allowed type with any gene
                    feasible_types = list(allowed_types)

                mtype = rng_py.choice(feasible_types)

                if mtype in ("LOCK_HI", "LOCK_LO"):
                    # Pick from pre-confirmed effective targets first
                    matching = [(gid, mt) for gid, mt in gene_pool if mt == mtype]
                    if matching:
                        target_id, _ = rng_py.choice(matching)
                    else:
                        # Fall back: any phenotype gene
                        target_id = rng_py.choice(phenotype_gene_ids or gene_ids)
                    target_name = gene_id_to_name[target_id]
                    bias = BIAS_SEVERITY if mtype == "LOCK_HI" else -BIAS_SEVERITY
                    perturbed_rule[target_id]["bias"] = bias
                    label = "Node locked high" if mtype == "LOCK_HI" else "Node locked low"
                    malfunctions.append(Malfunction(
                        type=mtype,
                        target=target_id,
                        target_name=target_name,
                        severity=BIAS_SEVERITY,
                        description=f"{label}: {target_name} ({mtype})",
                    ))

                else:  # PERSIST
                    if signal_pool:
                        sig_id = rng_py.choice(signal_pool)
                    elif signal_ids:
                        sig_id = rng_py.choice(signal_ids)
                    else:
                        # No signals at all — fallback to LOCK_HI on phenotype gene
                        if phenotype_gene_ids:
                            target_id = rng_py.choice(phenotype_gene_ids)
                            target_name = gene_id_to_name[target_id]
                            perturbed_rule[target_id]["bias"] = BIAS_SEVERITY
                            malfunctions.append(Malfunction(
                                type="LOCK_HI",
                                target=target_id,
                                target_name=target_name,
                                severity=BIAS_SEVERITY,
                                description=f"Node locked high: {target_name} (LOCK_HI)",
                            ))
                            continue
                        continue

                    sig_label = signal_id_to_label[sig_id]
                    orig_sig = next(s for s in org.signals if s.id == sig_id)
                    severity = 10.0
                    new_strength = orig_sig.strength * severity
                    chronic_signal_overrides[sig_id] = (
                        new_strength if orig_sig.mode == "activates" else -new_strength
                    )
                    malfunctions.append(Malfunction(
                        type="PERSIST",
                        target=sig_id,
                        target_name=sig_label,
                        severity=severity,
                        description=f"Persistent {sig_label} signal ({severity}x normal strength)",
                    ))

            # Build a temporary organism with the perturbed rule
            import copy as _copy
            perturbed_dynamics = _copy.deepcopy(org.dynamics)
            perturbed_dynamics.rule = perturbed_rule
            org_perturbed = Organism(
                id=org.id,
                genes=org.genes,
                modules=org.modules,
                signals=org.signals,
                relations=org.relations,
                phenotypes=org.phenotypes,
                dynamics=perturbed_dynamics,
                seed=org.seed,
                baseline_state=healthy_baseline,
                observable_genes=org.observable_genes,
            )

            result = simulate_sigmoid(
                org_perturbed,
                interventions={},
                active_signals=chronic_signal_overrides,
                rng=np.random.default_rng(seed + 1234),
            )
            disease_baseline = result["final_state"]
            disease_phenos = compute_phenotypes(org_perturbed, disease_baseline, noise=False)

            # Check condition 1: ≥1 phenotype outside healthy range
            aberrant = [
                label for label, val in disease_phenos.items()
                if not (
                    healthy_phenotype_ranges[label][0]
                    <= val
                    <= healthy_phenotype_ranges[label][1]
                )
            ]
            if not aberrant:
                continue

            # Check condition 2: a corrective single-intervention can restore ≥1 phenotype
            if _verify_rescue_combo(malfunctions, org_perturbed, aberrant, chronic_signal_overrides):
                return malfunctions, disease_baseline, perturbed_dynamics, chronic_signal_overrides

            # Aberrant but not rescuable — keep as fallback, try again
            if last_aberrant_result is None:
                last_aberrant_result = (
                    malfunctions, disease_baseline, perturbed_dynamics, chronic_signal_overrides,
                )

        # Could not satisfy both conditions — return best aberrant result or last attempt
        import warnings
        if last_aberrant_result is not None:
            warnings.warn(
                "generate_disease_organism: Found aberrant phenotypes but could not verify "
                "a rescuable single-intervention after max_attempts. Detectability guarantee "
                "may not hold. Consider using a different seed or organism configuration.",
                UserWarning,
                stacklevel=3,
            )
            return last_aberrant_result
        warnings.warn(
            "generate_disease_organism: No aberrant phenotypes produced after max_attempts. "
            "Returning last attempt. The malfunction may be too weak for this network.",
            UserWarning,
            stacklevel=3,
        )
        return malfunctions, disease_baseline, perturbed_dynamics, chronic_signal_overrides

    malfunctions, disease_baseline, perturbed_dynamics, _ = _apply_malfunctions(n_malfunctions)

    # Update organism in-place: disease state is the new baseline
    org.dynamics = perturbed_dynamics
    org.baseline_state = disease_baseline
    org.cell_type = cell_type
    org.healthy_baseline = healthy_baseline
    org.healthy_phenotype_ranges = healthy_phenotype_ranges
    org.malfunctions = malfunctions

    # Preserve detectability guarantee: malfunction target genes must never be latent
    # (the agent needs to be able to target them for rescue).
    if org.latent_genes:
        malfunction_targets = {m.target for m in malfunctions if m.type in ("LOCK_HI", "LOCK_LO")}
        org.latent_genes = [gid for gid in org.latent_genes if gid not in malfunction_targets]

    return org
