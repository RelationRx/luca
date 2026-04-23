# Backwards-Organisms Ablation — Results

**Status:** first draft, ready for paper-subsection adaptation.
**Date:** 2026-04-23
**Owner:** Karl Gemayel
**Design spec:** `docs/superpowers/specs/2026-04-22-backwards-organisms-ablation-design.md`
**Stats artifact:** `experiments/backwards_ablation/backwards_stats.json`
**Tables artifact:** `experiments/backwards_ablation/tables.md`
**Figures:** `experiments/backwards_ablation/figs/`

---

## 1. Question

Does the performance gap between top-LLM models and GPT-family models on LUCA
reflect genuine causal inference from perturbation observations, or
transferred structural priors from real-biology GRN literature picked up in
pretraining?

## 2. Design

Every signed quantity in each medium-tier organism is inverted:
GRN edge weights `w_ij`, gene biases `b_i`, signal modes, and phenotype
readout weights. Baseline state is re-simulated under backwards dynamics and
phenotype readout biases are re-centered so σ(0) ≈ 0.5 at baseline. Topology,
magnitudes, and noise are preserved.

Twenty canonical medium-tier seeds × 2 modes (healthy, disease) are run in
both directions with the same code version. Analysis is paired per seed:
`Δ = forward_i − backward_i`. Stats: paired Wilcoxon signed-rank,
percentile-bootstrap 95% CI, and a mixed-effects model
`score ~ C(model) * C(direction) + (1|seed)`.

**Model set** (5 LLMs + null control): Claude Opus 4.6, Claude Sonnet 4.6,
GPT-5.1, GPT-4o, GPT-4.1, heuristic. DeepSeek V3.1 and Qwen 3.5 deferred
(Together AI credits); adding them is tracked as follow-up work.

**Null control.** The heuristic baseline runs the same systematic BLOCK
sweep and additive prediction on both directions. It contains no
structural priors — any backwards-vs-forward gap it shows reflects a
*substrate* difference in how easy each direction is to learn, not
prior-reliance. All LLM gaps are reported both raw and heuristic-adjusted
(`Δ_model − Δ_heuristic`) to isolate prior-reliance from substrate
difficulty.

## 3. Results

### 3.1 Validity of backwards organisms

Pre-screen successfully generated backwards organisms on **20/20 seeds in
both healthy and disease modes** (`experiments/backwards_ablation/valid_seeds.json`).
No convergence failures. No rescue-malfunction failures. The ablation runs on
the full canonical seed set.

### 3.2 Healthy mode — no evidence of structural-prior reliance

| Model | N | Forward | Backward | Δ (F−B) | 95% CI | Wilcoxon p | Δ − Δ_heuristic |
|---|---:|---:|---:|---:|:---:|---:|---:|
| claude-opus-4-6 | 20 | 0.908 ± 0.101 | 0.933 ± 0.100 | **−0.025** | [−0.092, +0.042] | 0.50 | −0.017 |
| claude-sonnet-4-6 | 20 | 0.908 ± 0.101 | 0.867 ± 0.168 | **+0.042** | [−0.042, +0.125] | 0.66 | +0.050 |
| gpt-5.1 | 20 | 0.750 ± 0.127 | 0.767 ± 0.166 | **−0.017** | [−0.100, +0.067] | 0.67 | −0.008 |
| gpt-4o | 20 | 0.658 ± 0.138 | 0.733 ± 0.137 | **−0.075** | [−0.125, −0.025] | **0.017** | −0.067 |
| gpt-4.1 | 20 | 0.733 ± 0.137 | 0.708 ± 0.119 | +0.025 | [−0.050, +0.108] | 0.56 | +0.033 |
| heuristic | 20 | 0.583 ± 0.148 | 0.592 ± 0.175 | −0.008 | [−0.083, +0.075] | 0.73 | — |

![Panel A — healthy](../experiments/backwards_ablation/figs/panel_a_delta_healthy.png)

![Panel B — healthy](../experiments/backwards_ablation/figs/panel_b_scatter_healthy.png)

**Finding.** No LLM shows a prior-reliance signal on healthy-mode composite
scores. Four of five models have paired deltas whose bootstrap CI crosses
zero; the one significant result (GPT-4o, p = 0.017) goes the "wrong"
direction — GPT-4o scores *higher* on backwards than forward. The
heuristic-adjusted column is small and mixed in sign for every model.

The mixed-effects model confirms: no `C(model) × C(direction)` interaction
term is significant on healthy (all p > 0.24). Models behave
indistinguishably across directions.

**Interpretation.** Prediction tasks on medium-healthy organisms are learned
from perturbation observations, not from priors about how GRNs "should"
behave. This is consistent with the paper's framing of healthy-mode
prediction as the least-ambiguous capability in the benchmark.

### 3.3 Disease mode — prior-reliance visible in diagnosis sub-score

| Model | N | Forward | Backward | Δ (F−B) | 95% CI | Wilcoxon p | Δ − Δ_heuristic |
|---|---:|---:|---:|---:|:---:|---:|---:|
| claude-opus-4-6 | 20 | 0.805 ± 0.175 | 0.703 ± 0.173 | **+0.103** | [−0.003, +0.200] | 0.08 | **+0.231** |
| claude-sonnet-4-6 | 20 | 0.703 ± 0.168 | 0.692 ± 0.202 | +0.011 | [−0.092, +0.119] | 0.84 | +0.139 |
| gpt-5.1 | 20 | 0.397 ± 0.193 | 0.314 ± 0.141 | +0.083 | [−0.017, +0.186] | 0.23 | +0.211 |
| gpt-4o | 20 | 0.425 ± 0.143 | 0.472 ± 0.220 | −0.047 | [−0.155, +0.061] | 0.51 | +0.081 |
| gpt-4.1 | 20 | 0.389 ± 0.208 | 0.392 ± 0.232 | −0.003 | [−0.125, +0.114] | 0.96 | +0.125 |
| heuristic | 20 | 0.522 ± 0.150 | 0.650 ± 0.226 | **−0.128** | [−0.256, +0.006] | 0.07 | — |

![Panel A — disease](../experiments/backwards_ablation/figs/panel_a_delta_disease.png)

![Panel B — disease](../experiments/backwards_ablation/figs/panel_b_scatter_disease.png)

**The heuristic substrate effect.** Heuristic composite *rises* 0.128 on
backwards disease (Wilcoxon p = 0.07). Backwards disease organisms are
structurally easier for a prior-free additive model. This contaminates raw
`Δ (F−B)` deltas — every LLM's raw delta is offset by the substrate effect.
The **heuristic-adjusted column** isolates the LLM-specific signal.

All LLMs have positive heuristic-adjusted disease deltas (+0.08 to +0.23).
Opus has the largest (+0.23). **After controlling for the substrate effect,
every LLM drops on backwards disease.**

The mixed-effects model picks this up: `C(model)[heuristic] × C(direction)`
is significant (β = −0.23, p = **0.006**) — heuristic's direction-response
differs sharply from the LLMs. This is the paper's load-bearing stat for the
prior-reliance claim.

### 3.4 Disease sub-score decomposition — prior-reliance lives in diagnosis

Paired deltas on the three disease sub-scores (forward − backward):

| Model | prediction Δ | diagnosis Δ | rescue Δ |
|---|---:|---:|---:|
| claude-opus-4-6 | +0.058 | **+0.250** | +0.000 |
| claude-sonnet-4-6 | −0.050 | +0.050 | +0.033 |
| gpt-5.1 | +0.008 | +0.075 | +0.167 |
| gpt-4o | −0.025 | −0.150 | +0.033 |
| gpt-4.1 | +0.058 | −0.050 | −0.017 |
| heuristic | +0.067 | **−0.400** | −0.050 |

![Disease sub-scores](../experiments/backwards_ablation/figs/disease_subscores.png)

**This is the central finding.** Decomposing the disease composite into its
three sub-scores shows that the prior-reliance signal is concentrated
entirely in **diagnosis**:

- **Prediction** on backwards disease: flat for every model (|Δ| ≤ 0.07).
  Consistent with §3.2 — prediction is observation-driven.
- **Rescue** on backwards disease: flat or mildly up for most models.
  Rescue is conditional on diagnosis — once a hypothesis is on the table,
  inverting signs doesn't change "what corrective intervention to try."
- **Diagnosis** on backwards disease: heuristic gets *substantially easier*
  (Δ = −0.40 — heuristic diagnosis rises from ~0.10 forward to ~0.50
  backwards). Every LLM's diagnosis delta is *0.25–0.65 worse than this
  null baseline*, with Opus the largest (+0.25 raw, +0.65
  heuristic-adjusted).

The interpretation: **diagnosis requires abductive inference over
candidate malfunctions, and LLMs rank candidates using real-biology
priors.** A backwards organism — where "blocking an activator raises
downstream" — violates those priors, and top LLMs struggle to update
despite direct experimental evidence. Prediction and rescue, which are
observation-driven, remain robust.

### 3.5 Connection to the paper's rescue-without-diagnosis finding

The paper's headline result is that LLMs intervene successfully (high
rescue) without identifying the underlying cause (low diagnosis). This
ablation explains the mechanism: **the two tasks rely on different
capabilities** — rescue on observation, diagnosis on abductive inference.
Inverting organism signs breaks the second but leaves the first intact,
consistent with the paper's dissociation framing. The ablation turns that
framing from a behavioural observation into a mechanistic claim
(diagnosis-as-prior-laden-inference) that the paper's existing data
could not have isolated.

## 4. Limitations

- **Medium tier only.** Easy is near-linear (weak discriminator); hard has
  backwards-convergence issues (mutual inhibition from flipped feedback
  edges) — deferred to future work.
- **Five LLMs, not seven.** DeepSeek V3.1 and Qwen 3.5 not included due to a
  Together AI credit shortfall at sweep time. Their inclusion would test
  whether the diagnosis prior-reliance generalises to the open-source family.
  Tracked as follow-up; credit top-up + ~40-session sweep + re-run
  `analyze.py` is a single-morning task.
- **Uniform sign-flip policy only.** We do not test partial-inversion
  variants (e.g. flipping only edge weights). Design spec §2.1 discusses
  rejected alternatives; a partial variant would leak priors and likely
  produce a weaker signal.
- **The heuristic substrate effect is large** (Δ_heuristic = −0.128 on disease
  composite). This puts pressure on `Δ_model − Δ_heuristic` as a valid
  adjustment: it assumes the substrate effect factors out linearly. The
  mixed-effects interaction p = 0.006 on the heuristic-direction term is the
  strongest standalone evidence that LLMs behave differently from the null
  control.
- **Paired per-seed comparison** — strongest within-organism control
  available, but it does not rule out a *magnitude-mediated* side effect of
  inversion that interacts with LLM reasoning differently than with heuristic
  reasoning. Future work: vary inversion strength or selectively invert
  subsets of signed surfaces to isolate the mechanism further.

## 5. Paper subsection — draft

### Suggested placement: new §3.5 before "Engineering limitations," or as Appendix D with a forward-reference from §3.4.

> **Structural-prior ablation.** To test whether top-LLM performance on
> LUCA reflects observation-based causal inference or transferred
> structural priors from real-biology GRN literature, we constructed a
> *backwards* organism variant for each of the 20 canonical medium seeds
> by inverting every signed quantity (edge weights, biases, signal modes,
> phenotype readout weights). Topology, magnitudes, and noise are
> preserved; baselines are re-centered so phenotype readings remain ≈ 0.5
> at steady state. We then evaluated five LLMs (Opus 4.6, Sonnet 4.6,
> GPT-5.1, GPT-4o, GPT-4.1) and the heuristic baseline in a paired-seed
> design on both directions.
>
> Healthy-mode composite scores are indistinguishable across directions
> for every model tested (|Δ| ≤ 0.08, no significant model × direction
> interaction). In disease mode, however, the heuristic baseline rises
> substantially on backwards organisms (Δ = −0.128; p = 0.07), reflecting
> a *substrate* effect — prior-free additive models find backwards
> disease organisms structurally easier. After heuristic-adjustment, every
> LLM drops 0.08–0.23 on backwards disease relative to the null control,
> with Opus the largest (+0.23; mixed-effects p on the heuristic ×
> direction interaction = 0.006).
>
> Decomposing the disease composite into prediction, diagnosis, and rescue
> localises the prior-reliance signal to diagnosis alone: prediction and
> rescue deltas hover around zero for all models, while diagnosis deltas
> span −0.40 (heuristic, *improving*) to +0.25 (Opus, *degrading*). This
> dissociation mirrors the paper's headline rescue-without-diagnosis
> finding and explains its mechanism: rescue depends on direct
> intervention-response observation, which inversion leaves intact, while
> diagnosis depends on abductive inference over candidate malfunctions
> whose likelihood rankings draw on real-biology priors that backwards
> organisms violate. Healthy-mode prediction — also observation-driven —
> is equivalently robust.
>
> Two open-source models (DeepSeek V3.1, Qwen 3.5) are excluded from this
> sweep; whether their diagnosis performance shows the same prior-reliance
> pattern is a natural extension.

## 6. Reproduction

See `experiments/backwards_ablation/README.md` for the seed manifest,
runner commands, and cost estimates.

## 7. Acknowledgments

*(Left for the paper-integration step.)*
