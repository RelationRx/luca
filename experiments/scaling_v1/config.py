"""
Scaling study v1 — network size sweep at fixed difficulty (medium, healthy).

Design
------
Vary N (number of genes) from 20 to 1280 while holding difficulty=medium, mode=healthy.
All complexity axes (FFL density, feedback density, observability) scale as
fractions of N, so the GRN structure grows proportionally.

Budget formula: B = N + N_signals + 8  (N_signals ≈ N/7)
Observable genes: 60% × N (medium tier)

N_GENES values and implied budget / observable counts:
  N=20:   budget=31,   observable=12
  N=40:   budget=54,   observable=24
  N=80:   budget=99,   observable=48
  N=160:  budget=191,  observable=96
  N=320:  budget=374,  observable=192
  N=640:  budget=740,  observable=384
  N=1280: budget=1471, observable=768

Models (all N values):
  claude-sonnet-4-6  — primary LLM agent
  gpt-4o             — cross-family comparison (included at N=1280 as exploratory)
  heuristic          — structured baseline (systematic BLOCK + additive prediction)
  random             — chance baseline (predict 0.5, no experiments)

Seeds: 0–9 (10 per sweep, consistent with Part 1 medium healthy).
"""
from __future__ import annotations

N_GENES = [20, 40, 80, 160, 320, 640, 1280]

SEEDS = list(range(10))

MODELS = [
    "claude-sonnet-4-6",
    "gpt-4o",
    "heuristic",
    "random",
]

SWEEPS: dict[str, dict] = {
    f"N{n:03d}": dict(
        n_genes=n,
        difficulty="medium",
        disease=False,
        seeds=SEEDS,
        models=MODELS,
    )
    for n in N_GENES
}
