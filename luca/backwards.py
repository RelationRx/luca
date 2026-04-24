"""Backwards-organism transform for structural-prior ablation.

Pure function `invert_organism(org)` returns a copy of the input organism with
every signed quantity flipped: GRN edge weights, gene biases, signal modes,
and phenotype readout weights. After flipping, baseline state is re-simulated
under the new dynamics and phenotype readout biases are re-centered so
baseline phenotypes ≈ 0.5. Latent-gene detectability is re-verified and
repaired if needed (same functional probe as `generation.py`).
"""
from __future__ import annotations

import copy

import numpy as np

from .schema import Organism


def invert_organism(org: Organism) -> Organism:
    """Return a copy of `org` with all signed quantities flipped.

    Flipped surfaces:
      1. GRN edge weights (dynamics.rule[*].inputs[*].weight)
      2. Gene biases (dynamics.rule[*].bias)
      3. GRN edge labels (relations[*].type)
      4. Signal modes (signals[*].mode)
      5. Phenotype readout weights (phenotypes[*].readout.weights)

    After flipping, baseline state is re-simulated under the new dynamics
    and phenotype readout biases are re-centered so baseline phenotypes ≈ 0.5.
    Latent-gene detectability is re-verified.

    Raises:
        ValueError: if called on a disease organism (has malfunctions or
            healthy_baseline). Use generate_disease_organism(backwards=True)
            instead.
    """
    if org.malfunctions or org.healthy_baseline:
        raise ValueError(
            "invert_organism() is for healthy organisms only. "
            "For disease organisms, use generate_disease_organism(backwards=True) "
            "which inverts the underlying healthy organism before applying "
            "malfunctions."
        )

    org = copy.deepcopy(org)

    # 1. GRN edge weights + gene biases
    for dst, r in org.dynamics.rule.items():
        r["bias"] = -r["bias"]
        for inp in r.get("inputs", []):
            inp["weight"] = -inp["weight"]

    # 2. Relation labels (organism self-description)
    for rel in org.relations:
        rel.type = "inhibits" if rel.type == "activates" else "activates"

    # 3. Signal modes
    for sig in org.signals:
        sig.mode = "inhibits" if sig.mode == "activates" else "activates"

    # 4. Phenotype readout weights
    for ph in org.phenotypes:
        ph.readout.weights = [-w for w in ph.readout.weights]

    # 5. Re-simulate baseline under backwards dynamics
    from .dynamics import simulate_sigmoid
    rng = np.random.default_rng(org.seed)
    result = simulate_sigmoid(org, interventions={}, active_signals={}, rng=rng)
    org.baseline_state = result["final_state"]

    # 5b. Re-verify latent-gene detectability under backwards dynamics.
    #     Port of generation.py step 12 (lines 402-460). No-op on medium tier
    #     (latent_fraction=0). Under dense-feedback backwards dynamics (hard
    #     tier) the simulator may return non-convergent states; repair runs
    #     anyway, but effectiveness is not guaranteed there — hard tier is
    #     out of scope for the backwards ablation.
    _repair_latent_detectability(org)

    # 6. Re-center phenotype readout biases so σ(0) = 0.5 at baseline.
    #    Runs after latent repair so any newly-added readout contributions
    #    are absorbed. Mirrors generation.py step 13 (lines 473-476).
    for ph in org.phenotypes:
        ro = ph.readout
        S = sum(
            w * org.baseline_state.get(gid, 0.0)
            for gid, w in zip(ro.depends_on, ro.weights)
        )
        ro.bias = float(-S)

    return org


LATENT_EFFECT_THRESHOLD = 0.05


def _repair_latent_detectability(org: Organism) -> None:
    """Ensure every latent gene has a measurable phenotype effect.

    If BLOCKing a latent gene shifts no phenotype by more than
    LATENT_EFFECT_THRESHOLD, add the latent gene as a direct contributor to
    the phenotype with fewest current contributors.

    Port of generation.py:402-460, adapted for post-inversion state. Mutates
    `org` in place. No-op when `org.latent_genes` is empty (e.g. medium tier).
    """
    from .dynamics import compute_phenotypes, simulate_sigmoid

    if not org.latent_genes:
        return

    n_rel = max(len(org.relations), 1)
    backward_inhibition_fraction = sum(
        1 for rel in org.relations if rel.type == "inhibits"
    ) / n_rel

    rng_add = np.random.default_rng(org.seed ^ 0xBEEF)
    baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    ph_labels = list(baseline_phenos.keys())

    for latent_id in org.latent_genes:
        blocked = simulate_sigmoid(
            org,
            interventions={latent_id: {"type": "BLOCK"}},
            active_signals={},
            rng=np.random.default_rng(org.seed ^ 0xDEAD),
        )
        blocked_phenos = compute_phenotypes(org, blocked["final_state"], noise=False)
        max_shift = max(
            abs(blocked_phenos.get(lbl, 0.5) - baseline_phenos.get(lbl, 0.5))
            for lbl in ph_labels
        )
        if max_shift > LATENT_EFFECT_THRESHOLD:
            continue

        k = min(
            range(len(org.phenotypes)),
            key=lambda i: len(org.phenotypes[i].readout.depends_on),
        )
        ph = org.phenotypes[k]
        strength = float(rng_add.uniform(0.7, 1.5))
        sign = -1.0 if rng_add.random() < backward_inhibition_fraction else 1.0
        ph.readout.depends_on.append(latent_id)
        ph.readout.weights.append(sign * strength)
        baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
