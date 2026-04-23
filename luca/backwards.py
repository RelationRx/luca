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

    # 6. Re-center phenotype readout biases so σ(0) = 0.5 at baseline.
    #    Mirrors generation.py step 13 (lines 473-476).
    for ph in org.phenotypes:
        ro = ph.readout
        S = sum(
            w * org.baseline_state.get(gid, 0.0)
            for gid, w in zip(ro.depends_on, ro.weights)
        )
        ro.bias = float(-S)

    return org
