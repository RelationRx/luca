"""Backwards-organism transform for structural-prior ablation.

Pure function `invert_organism(org)` returns a copy of the input organism with
every signed quantity flipped: GRN edge weights, gene biases, signal modes,
and phenotype readout weights. After flipping, baseline state is re-simulated
under the new dynamics and phenotype readout biases are re-centered so
baseline phenotypes ≈ 0.5. Latent-gene detectability is re-verified and
repaired if needed (same functional probe as `generation.py`).
"""
from __future__ import annotations

from .schema import Organism


def invert_organism(org: Organism) -> Organism:
    """Return a copy of `org` with all signed quantities flipped."""
    raise NotImplementedError
