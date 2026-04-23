# Backwards-Organisms Ablation — Results

**Status:** placeholder — sweep not yet run. Fill this in after running:

```bash
python experiments/backwards_ablation/prescreen.py
python experiments/backwards_ablation/run.py --model …
python experiments/backwards_ablation/analyze.py
python experiments/backwards_ablation/plot.py
```

This document becomes the draft for the paper's backwards-ablation subsection.
Design spec: `docs/superpowers/specs/2026-04-22-backwards-organisms-ablation-design.md`.

---

## 1. Question

Does the performance gap between top-LLM models (Opus, DeepSeek, Sonnet,
Qwen) and GPT-family models on LUCA reflect genuine causal inference from
perturbation observations, or transferred structural priors from real-biology
GRN literature?

## 2. Design

Every signed quantity in each medium-tier organism is inverted: GRN edge
weights `w_ij`, gene biases `b_i`, signal modes, and phenotype readout
weights. Baseline state is re-simulated under backwards dynamics and
phenotype readout biases are re-centered so σ(0) ≈ 0.5 at baseline. Topology,
magnitudes, and noise are preserved.

For each of the 20 canonical medium seeds × 2 modes (healthy, disease), we
compare each model's composite score on the forward organism (from the
paper's existing sweep) with its composite score on the backwards twin.
Heuristic is included as a null control: additive prediction fits observed
data, not structural priors, so its gap should be near zero.

**Prediction under the "genuine reasoning" hypothesis:** top-LLM gap ≈ 0.
**Prediction under the "transferred priors" hypothesis:** top-LLM gap > 0,
heuristic gap ≈ 0.

## 3. Results

### 3.1 Validity of backwards organisms

*(To fill in: N valid seeds per cell. Pre-screen reported __/20 for
medium_healthy and __/20 for medium_disease.)*

### 3.2 Paired composite-score deltas

*(To fill in. Tables generated from `backwards_stats.json` — see
`experiments/backwards_ablation/tables.md`.)*

![Panel A — structural-prior reliance](../experiments/backwards_ablation/figs/panel_a_delta_healthy.png)

### 3.3 Forward vs backwards scatter

*(To fill in.)*

![Panel B — forward vs backward scatter](../experiments/backwards_ablation/figs/panel_b_scatter_healthy.png)

### 3.4 Disease-mode sub-scores

*(To fill in. Most interesting comparison: diagnosis-score gap, which isolates
Claude's abductive reasoning from its rescue-planning performance.)*

![Disease sub-scores](../experiments/backwards_ablation/figs/disease_subscores.png)

### 3.5 Mixed-effects interaction

*(To fill in. Model × direction interaction from
`score ~ C(model) * C(direction) + (1|seed)`. Significant interaction →
models vary in their prior-reliance even after controlling for the main
effect of backwards being uniformly harder.)*

## 4. Interpretation

*(To fill in. Two scenarios to address explicitly:)*

**Scenario A — Claude ≈ 0, GPT > 0, heuristic ≈ 0.** Clean split. Supports
the paper's "genuine reasoning" framing for Claude; reframes the GPT gap as
prior-reliance rather than generic weakness.

**Scenario B — All LLMs > 0, heuristic ≈ 0.** All LLMs rely on priors to some
degree. Claude's advantage is smaller once priors are controlled for. Still a
publishable result — reframes the paper's main claim as "LLMs do both
observation-based reasoning *and* prior-reliance; the benchmark separates
them."

**Scenario C — All gaps including heuristic > 0.** Backwards organisms are
uniformly harder, not specifically prior-testing. The heuristic-adjusted
column (`Δ_model − Δ_heuristic`) isolates the LLM-specific reliance; that
column is the load-bearing result, not the raw gap.

## 5. Limitations

- **Medium tier only.** Easy is near-linear (weak discriminator); hard has
  backwards-convergence issues (mutual inhibition from flipped feedback
  edges) — deferred to future work.
- **Inversion policy.** Uniform sign-flip across all four signed surfaces.
  Partial inversions (e.g. edges only, keeping signals and readouts) would
  leak priors; maximal inversions (flipping FFL and feedback coherence
  structurally) risk breaking convergence. Briefly discussed in §2.1 of the
  design spec.
- **Paired comparison.** Same seed → same topology → forward vs backwards
  differ only in sign distribution. This is the strongest within-seed
  comparison available; it does not control for any *magnitude-mediated*
  effect of inversion on dynamics.

## 6. Reproduction

See `experiments/backwards_ablation/README.md`.

## 7. Acknowledgments

*(Left for the final paper version.)*
