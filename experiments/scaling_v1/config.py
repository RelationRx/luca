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

N_GENES = [20, 40, 80, 160, 320, 640, 1280]

SEEDS = list(range(10))
SEEDS_LARGE = list(range(5))  # 5 seeds for N>=320 (cost constraint)

# Core sweep: cheap, runs at all N values
CORE_MODELS = [
    "claude-sonnet-4-6",
    "heuristic",
    "random",
]

# Extended: Opus added at N>=160 — it's the leader and most informative at scale
EXTENDED_MODELS = [
    "claude-opus-4-6",
]

# GPT-4o added at N>=80 for cross-family comparison
GPT_MODELS = [
    "gpt-4o",
]

def _seeds(n: int) -> list[int]:
    return SEEDS if n <= 160 else SEEDS_LARGE

def _models(n: int) -> list[str]:
    if n < 160:
        return CORE_MODELS
    if n < 320:
        return CORE_MODELS + EXTENDED_MODELS
    return CORE_MODELS + EXTENDED_MODELS  # GPT-4o excluded at large N (context risk)

SWEEPS: dict[str, dict] = {
    f"N{n:03d}": dict(
        n_genes=n,
        difficulty="medium",
        disease=False,
        seeds=_seeds(n),
        models=_models(n),
    )
    for n in N_GENES
}
