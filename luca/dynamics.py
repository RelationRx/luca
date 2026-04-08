"""Continuous sigmoid simulation for LUCA organisms."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .schema import Organism


def sigmoid(z: float, steepness: float = 1.0) -> float:
    """Numerically stable sigmoid with adjustable steepness."""
    sz = steepness * z
    if sz >= 0:
        return 1.0 / (1.0 + math.exp(-sz))
    e = math.exp(sz)
    return e / (1.0 + e)


def simulate_sigmoid(
    organism: Organism,
    interventions: dict[str, Any] | None = None,
    active_signals: dict[str, float] | None = None,
    max_steps: int = 500,
    convergence_tol: float | None = None,
    rng: np.random.Generator | None = None,
) -> dict[str, Any]:
    """
    Run discrete-time sigmoid dynamics to convergence.

    interventions: {gene_id → {"type": "BLOCK"|"BOOST"|"DAMPEN"}}
    active_signals: {signal_id → strength}  (overrides signal.strength if provided)
    Returns: {final_state, steps, status, phenotypes}
    """
    if rng is None:
        rng = np.random.default_rng(None)

    rule = organism.dynamics.rule
    noise_sigma = organism.dynamics.noise_sigma
    steepness = organism.dynamics.sigmoid_steepness
    if convergence_tol is None:
        convergence_tol = organism.dynamics.convergence_tol
    gene_ids = [g.id for g in organism.genes]

    # Build signal contribution map: gene_id -> list of (strength_value)
    signal_contrib: dict[str, float] = {gid: 0.0 for gid in gene_ids}
    for sig in organism.signals:
        strength = active_signals.get(sig.id, sig.strength) if active_signals else sig.strength
        signed = strength if sig.mode == "activates" else -strength
        for target in sig.targets:
            if target in signal_contrib:
                signal_contrib[target] += signed

    # Initialize from baseline or uniform
    x: dict[str, float] = {}
    if organism.baseline_state:
        x = dict(organism.baseline_state)
    else:
        x = {gid: 0.5 for gid in gene_ids}

    # Apply BLOCK/BOOST clamp before first step
    interventions = interventions or {}

    def apply_interventions(state: dict[str, float]) -> dict[str, float]:
        for gid, iv in interventions.items():
            itype = iv["type"] if isinstance(iv, dict) else iv
            if itype == "BLOCK":
                state[gid] = 0.0
            elif itype == "BOOST":
                state[gid] = 1.0
        return state

    x = apply_interventions(x)

    status = "max_steps_reached"
    steps = 0
    for step in range(max_steps):
        # Noiseless update for convergence check
        x_det: dict[str, float] = {}
        for gid in gene_ids:
            r = rule.get(gid, {})
            bias = r.get("bias", 0.0)
            z = bias + signal_contrib.get(gid, 0.0)
            for inp in r.get("inputs", []):
                z += inp["weight"] * x.get(inp["src"], 0.0)
            x_det[gid] = sigmoid(z, steepness)
        x_det = apply_interventions(x_det)
        for gid, iv in interventions.items():
            itype = iv["type"] if isinstance(iv, dict) else iv
            if itype == "DAMPEN":
                x_det[gid] = min(x_det[gid], 0.15)

        # Convergence check on deterministic trajectory
        free_genes = [gid for gid in gene_ids if gid not in interventions]
        if free_genes:
            max_diff = max(abs(x_det[gid] - x[gid]) for gid in free_genes)
        else:
            max_diff = 0.0

        # Add noise on top of deterministic update for final state
        x_new: dict[str, float] = {}
        noise = rng.normal(0.0, noise_sigma, size=len(gene_ids))
        for i, gid in enumerate(gene_ids):
            x_new[gid] = float(np.clip(x_det[gid] + noise[i], 0.0, 1.0))
        x_new = apply_interventions(x_new)
        for gid, iv in interventions.items():
            itype = iv["type"] if isinstance(iv, dict) else iv
            if itype == "DAMPEN":
                x_new[gid] = min(x_new[gid], 0.15)

        x = x_new
        steps = step + 1
        if max_diff < convergence_tol:
            status = "converged"
            break

    # Compute phenotype readouts
    phenotype_values: dict[str, float] = {}
    phenotype_noise = rng.normal(0.0, noise_sigma * 2, size=len(organism.phenotypes))
    for j, phen in enumerate(organism.phenotypes):
        ro = phen.readout
        z = ro.bias
        for gid, w in zip(ro.depends_on, ro.weights):
            z += w * x.get(gid, 0.0)
        phenotype_values[phen.label] = float(np.clip(sigmoid(z, steepness) + phenotype_noise[j], 0.0, 1.0))

    return {
        "final_state": x,
        "steps": steps,
        "status": status,
        "phenotypes": phenotype_values,
    }


def compute_phenotypes(
    organism: Organism,
    state: dict[str, float],
    rng: np.random.Generator | None = None,
    noise: bool = True,
) -> dict[str, float]:
    """Compute phenotype readouts from a gene state dict."""
    if rng is None:
        rng = np.random.default_rng(None)
    noise_sigma = organism.dynamics.noise_sigma
    steepness = organism.dynamics.sigmoid_steepness
    out: dict[str, float] = {}
    for phen in organism.phenotypes:
        ro = phen.readout
        z = ro.bias
        for gid, w in zip(ro.depends_on, ro.weights):
            z += w * state.get(gid, 0.0)
        val = sigmoid(z, steepness)
        if noise:
            val += float(rng.normal(0.0, noise_sigma * 2))
        out[phen.label] = float(np.clip(val, 0.0, 1.0))
    return out
