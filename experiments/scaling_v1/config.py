"""
Scaling study v1 — network size sweep at fixed difficulty (medium, healthy).

Design
------
Vary N (number of genes) from 20 to 160 while holding difficulty=medium.
All complexity axes (FFL density, feedback density, observability) scale as
fractions of N, so the GRN structure grows proportionally.

Budget formula: B = N + N_signals + 8  (N_signals ≈ N/7)
Observable genes: 60% × N (medium tier)

N_GENES values and implied budget / observable counts:
  N=20:  budget=31,  observable=12
  N=40:  budget=54,  observable=24
  N=80:  budget=99,  observable=48
  N=160: budget=191, observable=96

Core models (every N):
  claude-sonnet-4-6, heuristic, random

Extended models (N=80, N=160 only — expensive, run after core results are in):
  claude-opus-4-6, gpt-4o

Seeds: 0–9 (10 per sweep). No pre-screening needed for healthy medium organisms.
"""
from __future__ import annotations

N_GENES = [20, 40, 80, 160]

SEEDS = list(range(10))

# Core sweep: cheap, runs at all N values
CORE_MODELS = [
    "claude-sonnet-4-6",
    "heuristic",
    "random",
]

# Extended sweep: add at N=80+ after core results confirm the scaling trend
EXTENDED_MODELS = [
    "claude-opus-4-6",
    "gpt-4o",
]

SWEEPS: dict[str, dict] = {
    f"N{n:03d}": dict(
        n_genes=n,
        difficulty="medium",
        disease=False,
        seeds=SEEDS,
        models=CORE_MODELS if n < 80 else CORE_MODELS + EXTENDED_MODELS,
    )
    for n in N_GENES
}
