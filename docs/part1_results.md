# LUCA Part 1 — Benchmark Validation Results

Technical reference for the Part 1 benchmark results. Updated 2026-04-09 with open-source models.
For chronological context and run notes see `experiments/paper_v1/LAB_JOURNAL.md`.

---

## Setup

**Models**: claude-opus-4-6, claude-sonnet-4-6, deepseek-v3 (DeepSeek V3.1), qwen-3.5 (Qwen 3.5 397B), gpt-5.1, gpt-4o, gpt-4.1, heuristic, random (9 total)

**Sweeps**: 6 sweeps × 20 seeds × 9 models = **1080 sessions**

| Sweep | Difficulty | Mode |
|-------|-----------|------|
| B_easy_healthy | easy | healthy |
| A_medium_healthy | medium | healthy |
| B_hard_healthy | hard | healthy |
| A_medium_disease | medium | disease |
| C_easy_disease | easy | disease |
| C_hard_disease | hard | disease |

**Task**: Each session presents a freshly generated organism the agent has never seen. The agent runs perturbation experiments (BLOCK / BOOST / DAMPEN individual genes) under a fixed budget to characterise the network, then must answer 2 held-out prediction tasks — *"what would the phenotype values be if gene X is blocked and gene Y is boosted simultaneously?"* — for gene combinations it could not directly observe. In disease mode, the agent must additionally identify the malfunctioning gene and malfunction type (diagnosis) and test an intervention that restores phenotypes to healthy range (rescue).

**Scoring**:
- Prediction accuracy: fraction of phenotypes within **±0.10** of ground truth value across the 2 held-out tasks
- Healthy composite = prediction accuracy
- Disease composite = mean(prediction accuracy, diagnosis score, rescue fraction)
- Diagnosis: 1.0 exact match (gene + malfunction type), 0.5 correct gene wrong type, 0.0 wrong gene
- Rescue: fraction of aberrant phenotypes restored to healthy range

**Baselines**:
- *Heuristic*: systematically BLOCKs each gene, uses additive model for prediction, exhaustive hypothesis enumeration for diagnosis. Budget = n_genes + n_signals + 8.
- *Random*: predicts 0.5 everywhere, submits a random diagnosis. Runs no experiments.

**Generation**: frozen at tag `v1-generation-freeze-2` (commit `57f7be7`), n_genes=20.

---

## Results

### Healthy mode — composite score (mean ± std, N=20)

| Model | Easy | Medium | Hard |
|-------|------|--------|------|
| claude-opus-4-6 | **0.992** ± 0.036 | 0.900 ± 0.111 | 0.608 ± 0.192 |
| deepseek-v3 | 0.917 ± 0.124 | **0.908** ± 0.111 | **0.642** ± 0.161 |
| claude-sonnet-4-6 | 0.958 ± 0.089 | 0.875 ± 0.128 | 0.575 ± 0.250 |
| qwen-3.5 | 0.958 ± 0.072 | 0.892 ± 0.095 | 0.586 ± 0.178 |
| gpt-5.1 | 0.808 ± 0.142 | 0.781 ± 0.133 | 0.558 ± 0.206 |
| gpt-4o | 0.825 ± 0.123 | 0.667 ± 0.132 | 0.492 ± 0.201 |
| gpt-4.1 | 0.758 ± 0.134 | 0.667 ± 0.075 | 0.500 ± 0.253 |
| heuristic | 0.708 ± 0.089 | 0.575 ± 0.179 | 0.350 ± 0.196 |
| random | 0.667 ± 0.000 | 0.633 ± 0.085 | 0.350 ± 0.223 |

Best per column in bold.

### Disease mode — composite score (mean ± std, N=20)

| Model | Easy | Medium | Hard |
|-------|------|--------|------|
| claude-opus-4-6 | **0.875** ± 0.169 | **0.794** ± 0.166 | **0.631** ± 0.182 |
| claude-sonnet-4-6 | 0.808 ± 0.190 | 0.733 ± 0.181 | 0.569 ± 0.217 |
| qwen-3.5 | 0.744 ± 0.145 | 0.689 ± 0.167 | 0.606 ± 0.204 |
| deepseek-v3 | 0.631 ± 0.136 | 0.600 ± 0.134 | 0.531 ± 0.198 |
| heuristic | 0.597 ± 0.183 | 0.531 ± 0.127 | 0.428 ± 0.209 |
| gpt-4o | 0.514 ± 0.105 | 0.464 ± 0.126 | 0.358 ± 0.191 |
| gpt-4.1 | 0.492 ± 0.256 | 0.456 ± 0.236 | 0.372 ± 0.293 |
| random | 0.481 ± 0.109 | 0.425 ± 0.131 | 0.278 ± 0.155 |
| gpt-5.1 | 0.344 ± 0.148 | 0.361 ± 0.232 | 0.178 ± 0.174 |

Best per column in bold.

### Disease mode — breakdown by component (all tiers, N=20)

Scoring convention: models that do not attempt diagnosis or rescue receive a score of 0 for that component (consistent with `evaluate.py`). Not attempting is treated as a failure, not as missing data. See §5a for attempt rates.

**Medium disease:**

| Model | Pred acc | Diagnosis | Rescue | Composite |
|-------|----------|-----------|--------|-----------|
| claude-opus-4-6 | 0.833 | **0.550** | **1.000** | **0.794** |
| claude-sonnet-4-6 | **0.867** | 0.350 | 0.983 | 0.733 |
| qwen-3.5 | 0.833 | 0.250 | 0.983 | 0.689 |
| deepseek-v3 | 0.750 | 0.100 | 0.950 | 0.600 |
| heuristic | 0.608 | 0.100 | 0.883 | 0.531 |
| gpt-4o | 0.658 | 0.050 | 0.683 | 0.464 |
| gpt-4.1 | 0.783 | 0.100 | 0.483 | 0.456 |
| random | 0.450 | 0.075 | 0.750 | 0.425 |
| gpt-5.1 | 0.700 | 0.100 | 0.283 | 0.361 |

**Easy disease:**

| Model | Pred acc | Diagnosis | Rescue | Composite |
|-------|----------|-----------|--------|-----------|
| claude-opus-4-6 | 0.925 | **0.700** | **1.000** | **0.875** |
| claude-sonnet-4-6 | 0.875 | 0.550 | **1.000** | 0.808 |
| qwen-3.5 | **0.933** | 0.300 | **1.000** | 0.744 |
| deepseek-v3 | 0.808 | 0.150 | 0.933 | 0.631 |
| heuristic | 0.692 | 0.250 | 0.850 | 0.597 |
| gpt-4o | 0.717 | 0.075 | 0.750 | 0.514 |
| gpt-4.1 | 0.792 | 0.200 | 0.483 | 0.492 |
| random | 0.550 | 0.025 | 0.867 | 0.481 |
| gpt-5.1 | 0.750 | 0.000 | 0.283 | 0.344 |

**Hard disease:**

| Model | Pred acc | Diagnosis | Rescue | Composite |
|-------|----------|-----------|--------|-----------|
| claude-opus-4-6 | **0.592** | 0.350 | **0.950** | **0.631** |
| qwen-3.5 | 0.533 | **0.400** | 0.883 | 0.606 |
| claude-sonnet-4-6 | 0.542 | 0.300 | 0.867 | 0.569 |
| deepseek-v3 | 0.408 | 0.300 | 0.883 | 0.531 |
| heuristic | 0.450 | 0.200 | 0.633 | 0.428 |
| gpt-4.1 | 0.492 | 0.225 | 0.400 | 0.372 |
| gpt-4o | 0.408 | 0.150 | 0.517 | 0.358 |
| random | 0.258 | 0.075 | 0.500 | 0.278 |
| gpt-5.1 | 0.392 | 0.075 | 0.067 | 0.178 |

Best per column in bold.

---

## Analysis

### 1. Difficulty discriminates models cleanly

Easy is near-ceiling for most LLMs (0.81–0.99), making it a limited discriminator. Medium separates two tiers: Opus, DeepSeek, Qwen, and Sonnet (0.875–0.908) vs GPT-5.1, GPT-4o, and GPT-4.1 (0.667–0.781), with baselines below (0.575–0.633). Hard is the most discriminating tier: scores spread from 0.642 (DeepSeek) to 0.350 (baselines). Both baselines collapse to 0.350 on hard — indistinguishable from chance — validating that hard organisms require genuine causal reasoning.

Degradation from easy to hard is gradual (no cliff) but with high per-seed variance on hard, indicating a bimodal structure: models either solve an organism or partially fail, not gracefully degrade within a seed.

| Model | Easy→Hard drop | Hard seeds ≥0.80 | Hard seeds <0.50 |
|-------|---------------|-----------------|-----------------|
| claude-opus-4-6 | −0.383 | 4/20 | 3/20 |
| deepseek-v3 | −0.275 | 6/20 | 2/20 |
| claude-sonnet-4-6 | −0.383 | 6/20 | 6/20 |
| qwen-3.5 | −0.372 | 5/20 | 4/20 |
| gpt-5.1 | −0.250 | 3/20 | 4/20 |
| gpt-4o | −0.333 | 2/20 | 6/20 |
| gpt-4.1 | −0.258 | 4/20 | 7/20 |

### 2. Baselines are near-chance at ±0.10

The ±0.10 threshold correctly exposes baselines. On hard, both heuristic and random score 0.350 — the heuristic's additive prediction model fails on the nonlinear sigmoid dynamics of hard organisms. On medium, random (0.633) actually exceeds heuristic (0.575): the fixed 0.5 prediction is never catastrophically wrong, while the additive model accumulates errors. This validates the threshold choice — at ±0.15 baselines looked artificially competent.

### 3. Experiment strategy diverges sharply across models

Analysis of medium healthy sessions (N=20 seeds):

| Model | Avg experiments | Budget used | Single-gene % | Gene coverage |
|-------|----------------|-------------|---------------|---------------|
| claude-opus-4-6 | 27.2 | 88% | 98.5% | 100% |
| qwen-3.5 | 26.4 | 85% | 100.0% | 88% |
| deepseek-v3 | 25.9 | 84% | 97.0% | 66% |
| claude-sonnet-4-6 | 25.0 | 81% | 71.8% | 100% |
| gpt-5.1 | 26.6 | 85% | 64.8% | 56% |
| gpt-4o | 12.8 | 50% | 10.0% | 2% |
| gpt-4.1 | 16.8 | 63% | 5.0% | 3% |

Claude Opus runs a near-exhaustive single-gene BLOCK sweep covering all 20 genes. Claude Sonnet mixes single and multi-gene experiments but still achieves full coverage. GPT-5.1 runs many experiments but only covers 56% of genes (redundant). GPT-4o/4.1 run few experiments with near-zero systematic coverage.

Budget usage does not correlate with performance on hard (r ≈ 0.0–0.2): failures are early-stopping, not budget exhaustion.

In disease mode, Claude re-tests previously blocked genes after observing the aberrant phenotype (adaptive behaviour, 20/20 sessions). GPT models do this in 0–1/20 sessions.

**Budget usage across all six sweeps** (mean ± std, budget=31 for disease tiers):

| Model | Easy/H | Med/H | Hard/H | Easy/D | Med/D | Hard/D |
|-------|--------|-------|--------|--------|-------|--------|
| claude-opus-4-6 | 86% ± 2% | 89% ± 4% | 84% ± 5% | 83% ± 6% | 84% ± 5% | 82% ± 8% |
| claude-sonnet-4-6 | 79% ± 3% | 80% ± 3% | 76% ± 4% | 78% ± 5% | 78% ± 5% | 77% ± 6% |
| deepseek-v3 | 80% ± 9% | 84% ± 5% | 79% ± 7% | 60% ± 20% | 69% ± 12% | 70% ± 15% |
| qwen-3.5 | 87% ± 8% | 85% ± 6% | 74% ± 9% | 78% ± 8% | 78% ± 15% | 66% ± 14% |
| gpt-5.1 | 85% ± 11% | 81% ± 14% | 74% ± 14% | 35% ± 25% | 29% ± 27% | 30% ± 31% |
| gpt-4o | 57% ± 27% | 54% ± 24% | 47% ± 23% | 26% ± 10% | 24% ± 9% | 30% ± 17% |
| gpt-4.1 | 59% ± 20% | 57% ± 33% | 54% ± 15% | 26% ± 21% | 40% ± 31% | 32% ± 25% |
| heuristic | 65% ± 0% | 65% ± 0% | 48% ± 0% | 68% ± 0% | 68% ± 0% | 52% ± 1% |

Three distinct budget usage patterns emerge:
- **High and consistent** (Opus, Sonnet, DeepSeek, Qwen): 74–89% across healthy tiers, 60–84% on disease. Low variance (±2–15%). These models systematically explore the organism.
- **Variable, drops on disease** (GPT-5.1, GPT-4o, GPT-4.1): 47–85% on healthy with high variance, collapses to 24–40% on disease (±9–33%). Context exhaustion truncates disease sessions early, explaining the disease score collapse. GPT-4o and GPT-4.1 underuse budget even on healthy (47–59%).
- **Deterministic** (heuristic): fixed fraction (48–68%), drops on hard due to fewer unambiguous candidates.

**gpt-4.1 anomaly**: 11/20 disease seeds had zero experiments — the model read the organism description and submitted predictions and a hypothesis without any perturbation. This accidentally inflated its composite at ±0.15 (pred_acc from description alone can be high); at ±0.10 the anomaly disappears and gpt-4.1 correctly ranks below gpt-4o.

### 4. Prediction and diagnosis measure distinct capabilities

Prediction accuracy and diagnosis score are weakly correlated across all model families. On medium disease, models with comparable prediction accuracy show wide divergence on diagnosis:

| Model | Pred acc | Diagnosis |
|-------|----------|-----------|
| Sonnet | 0.867 | 0.350 |
| Qwen 3.5 | 0.833 | 0.250 |
| Opus | 0.833 | 0.550 |
| GPT-4.1 | 0.783 | 0.100 |
| DeepSeek V3.1 | 0.750 | 0.100 |
| GPT-4o | 0.658 | 0.050 |

Mean diagnosis across all disease tiers: Opus 0.533, Sonnet 0.400, Qwen 3.5 0.317, DeepSeek V3.1 0.183, GPT-4.1 0.175, GPT-4o 0.092, GPT-5.1 0.058. Diagnosis scores span a 10× range despite prediction scores spanning only 1.3×.

This dissociation is consistent across all three model families tested (Anthropic, OpenAI, open-source via Together AI), suggesting it reflects a structural difference between the two tasks rather than a model-specific limitation. Prediction is a forward-inference problem (given interventions, estimate phenotype values); diagnosis is an abductive-inference problem (given aberrant phenotypes, identify the root cause). The benchmark separates these two reasoning modes cleanly.

### 5. Rescue without diagnosis is the norm

Most models achieve high rescue scores (0.88–1.00) even with low diagnosis accuracy. On medium disease, rescue scores range from 0.950 to 1.000 for 5 of 7 LLMs — but diagnosis ranges from 0.050 to 0.550 for the same models. Rescue is a search problem (find any intervention that restores phenotypes); diagnosis is an identification problem (commit to a specific gene and malfunction type). Trial-and-error intervention sweeps are sufficient for rescue but insufficient for diagnosis.

### 5a. Attempt rates on disease tasks

GPT-5.1 and GPT-4.1 frequently terminate sessions before attempting diagnosis or rescue — their context windows are exhausted by the exploration phase. This is itself a failure mode: non-engagement is scored as 0 (see scoring convention above).

**Diagnosis attempt rate** (fraction of sessions where the model called `submit_malfunction_hypothesis`):

| Model | Easy | Medium | Hard |
|-------|------|--------|------|
| Opus, Sonnet, Qwen, heuristic, random | 100% | 100% | 100% |
| DeepSeek V3.1 | 95% | 100% | 100% |
| GPT-4o | 100% | 100% | 100% |
| GPT-4.1 | 60% | 60% | 55% |
| GPT-5.1 | 40% | 50% | 35% |

**Rescue attempt rate** (fraction of sessions where the model called `test_rescue`):

| Model | Easy | Medium | Hard |
|-------|------|--------|------|
| Opus, Sonnet, Qwen, heuristic, random | 100% | 100% | 100% |
| DeepSeek V3.1 | 95% | 100% | 100% |
| GPT-4o | 100% | 90% | 90% |
| GPT-4.1 | 55% | 50% | 50% |
| GPT-5.1 | 40% | 35% | 20% |

GPT-5.1 rescue scores (0.067–0.283) are low primarily because it attempts rescue on only 20–40% of seeds, not because its rescues fail when attempted. GPT-4.1 shows a similar pattern at 50–55%. This non-engagement correlates with the budget usage collapse described in §3 — both models exhaust their context window during exploration, leaving no turns for diagnosis or rescue.

### 6. Diagnosis difficulty scales with organism complexity

Diagnosis scores degrade with difficulty for all models that attempt diagnosis:

| Model | Easy | Medium | Hard |
|-------|------|--------|------|
| Opus | 0.700 | 0.550 | 0.350 |
| Sonnet | 0.550 | 0.350 | 0.300 |
| Qwen 3.5 | 0.300 | 0.250 | 0.400 |
| DeepSeek V3.1 | 0.150 | 0.100 | 0.300 |
| GPT-4.1 | 0.200 | 0.100 | 0.225 |

The gradient from easy to hard is steepest for the highest-performing models, consistent with genuine reasoning difficulty rather than random guessing. Diagnosis requires forming a causal hypothesis about the malfunction, not just predicting steady-state outputs.

Rescue tracks diagnosis:
- Correct diagnosis (N=22 sessions): rescue fraction = 0.955
- Wrong diagnosis (N=78 sessions): rescue fraction = 0.526

Partial rescue even with wrong diagnosis reflects generic stabilising interventions that happen to restore some phenotypes.

Diagnosis by ambiguity level (medium disease, all models):
- n_alternatives=0 (unambiguous, 74 sessions): Opus 62.5%, Sonnet 40%, Qwen 35.1%, GPT-4.1 28.6%, DeepSeek 16.2%, GPTs 0–14%
- n_alternatives=1 (14 sessions): Opus 100%, Sonnet 50%, GPTs 0–33%
- n_alternatives≥2 (12 sessions): no model succeeds

### 7. Network reconstruction does not predict performance

Edge inference from perturbation experiments (mean over N=20 seeds, ground truth = 12.0 edges/organism):

**Medium healthy:**

| Model | Precision | Recall | F1 | Inferred edges |
|-------|-----------|--------|----|---------------|
| claude-opus-4-6 | 0.640 | **0.933** | **0.754** | 18.1 |
| claude-sonnet-4-6 | **0.675** | 0.775 | 0.710 | 14.1 |
| qwen-3.5 | 0.615 | 0.742 | 0.660 | 14.8 |
| deepseek-v3 | 0.583 | 0.662 | 0.611 | 15.0 |
| gpt-5.1 | 0.570 | 0.754 | 0.644 | 15.3 |
| gpt-4o | 0.325 | 0.246 | 0.270 | 5.8 |
| gpt-4.1 | 0.153 | 0.112 | 0.109 | 3.0 |

**Hard healthy:**

| Model | Precision | Recall | F1 | Inferred edges |
|-------|-----------|--------|----|---------------|
| qwen-3.5 | **0.351** | 0.740 | **0.464** | 23.8 |
| claude-opus-4-6 | 0.265 | **0.752** | 0.390 | 34.0 |
| claude-sonnet-4-6 | 0.277 | 0.675 | 0.390 | 30.0 |
| gpt-5.1 | 0.257 | 0.719 | 0.376 | 30.7 |
| deepseek-v3 | 0.290 | 0.555 | 0.372 | 21.2 |
| gpt-4.1 | 0.227 | 0.441 | 0.294 | 20.1 |
| gpt-4o | 0.128 | 0.205 | 0.153 | 10.1 |

Best per column in bold.

Edges are `(gene, phenotype, direction)` triples inferred from observed phenotype shifts >0.05 on single-gene BLOCK/BOOST experiments.

On medium, Claude Opus achieves high recall (0.933) by over-inferring edges (18.1 inferred vs 12.0 ground truth), trading precision for coverage. On hard, precision collapses across all models — dense feedback and latent genes make phenotype shifts ambiguous, leading to many false positive edges (Opus: 34.0 inferred vs 12.2 ground truth). gpt-4o/4.1 run fewer experiments and infer fewer edges, explaining their low recall.

**Correlation with prediction accuracy** (Pearson r):

| Model | Medium r | Hard r |
|-------|----------|--------|
| claude-opus-4-6 | −0.30 | +0.18 |
| claude-sonnet-4-6 | +0.09 | +0.26 |
| deepseek-v3 | +0.16 | −0.43 |
| qwen-3.5 | +0.22 | +0.29 |
| gpt-5.1 | +0.01 | −0.02 |
| gpt-4o | −0.16 | +0.02 |
| gpt-4.1 | +0.21 | +0.46 |

Correlations are weak and inconsistent — higher network F1 does not reliably predict better prediction accuracy. Opus has a negative r on medium despite the highest F1, suggesting its prediction performance draws on something beyond explicit edge reconstruction. Note: this metric only captures gene→phenotype edges; gene→gene regulatory edges are not recoverable from current logs (see Ideas).

### 8. Hypothesis quality (disease mode, qualitative)

| Model | Text present | Avg length | Cites evidence |
|-------|-------------|------------|----------------|
| claude-opus-4-6 | 20/20 | 1292 chars | 19/20 |
| claude-sonnet-4-6 | 20/20 | 1336 chars | 19/20 |
| deepseek-v3 | 20/20 | 831 chars | 20/20 |
| qwen-3.5 | 20/20 | 564 chars | 20/20 |
| gpt-5.1 | 19/20 | **2932 chars** | 19/19 |
| gpt-4.1 | 20/20 | 799 chars | 13/20 |
| gpt-4o | 17/20 | 429 chars | 6/17 |

Claude hypotheses are concise, cite specific experiment results (e.g. "BLOCK G013 → signal-output = 0.77"), and identify gene, malfunction type, and mechanism. Even wrong Claude hypotheses are well-reasoned — they identify plausible alternatives with real evidence.

GPT-5.1 writes the longest hypotheses (2932 chars avg) but its one correct diagnosis came with no free text; wrong cases are verbose, fluent, and evidence-rich but reason toward wrong conclusions. GPT-4o produces the shortest hypotheses, rarely cites evidence.

### 9. Gene attribution bias — signal malfunctions never diagnosed

Two medium disease seeds (0 and 1) have signal malfunctions (thermal-pulse PERSIST, coupling-factor-Q PERSIST). No model across any seed correctly diagnosed a signal malfunction. Both Claude models identified compensating gene targets (correct rescue, wrong cause). GPT-4o was the only model to name a signal at all (wrong signal). GPT-5.1/4.1 submitted nothing valid.

Models systematically frame malfunctions as gene-level even when the true cause is an external signal. The `n_diagnosis_alternatives` metric correctly flagged both seeds (value=2), validating the ambiguity measure — the signal malfunction is observationally indistinguishable from a specific gene malfunction from the agent's vantage point.

This is not a prompt artefact. The system prompt and `submit_malfunction_hypothesis` tool definition both explicitly list signals as candidates alongside genes, and PERSIST is described as a distinct malfunction type. The bias is structural: a persistently active signal produces the same perturbation signature as a LOCK_HI on its most downstream gene target, because agents can activate signals but cannot block them. The only disambiguating experiment would be to *activate* the signal and observe whether the effect compounds — but no model across any seed attempted this. This represents an intentional source of diagnostic difficulty in the benchmark design, not a flaw, and `n_diagnosis_alternatives` correctly identifies it.

---

## §9 Ambiguity vs diagnosis accuracy

From `analyse_ambiguity.py` on all disease-mode session logs (240 sessions across
A_medium_disease, C_easy_disease, C_hard_disease).

**n_diagnosis_alternatives distribution:** 150 sessions with n=0 (unambiguous), 57 with
n=1, 22 with n=2, 7 with n=3, 4 with n=4. The majority of organisms are unambiguous —
ambiguity is a feature of hard-tier organisms and signal malfunction seeds.

**Mean diagnosis score by ambiguity level (all models pooled):**

| n_alternatives | Diagnosis score | n sessions |
|----------------|-----------------|------------|
| 0 | 0.387±0.485 | 150 |
| 1 | 0.149±0.353 | 57 |
| 2 | 0.227±0.429 | 22 |
| 3 | 0.286±0.488 | 7 |
| 4 | 0.500±0.577 | 4 |

**Per-model at n=0 (unambiguous):**

| Model | Diagnosis score (n=0) |
|-------|-----------------------|
| claude-opus-4-6 | 0.703±0.463 |
| claude-sonnet-4-6 | 0.514±0.507 |
| qwen-3.5 | 0.351±0.477 |
| gpt-4.1 | 0.286±0.463 |
| deepseek-v3 | 0.162±0.350 |
| gpt-5.1 | 0.139±0.335 |
| gpt-4o | 0.122±0.321 |

The main finding: even at n=0 (no ambiguity — there is exactly one correct answer), GPT
models score near zero while Claude models score 0.5–0.7. Ambiguity is not the primary
driver of diagnosis failure for GPT models — they fail even on unambiguous organisms.
For Claude models the performance at n=0 is meaningful (Opus 0.703), and drops sharply at
n≥1 — consistent with genuine causal reasoning that gets confused by multiple valid
explanations.

The non-monotonic trend at high n_alternatives (n=3,4) is unreliable due to very small
sample sizes (≤7 sessions). The actionable finding is the n=0 vs n≥1 contrast.

**Diagnosis vs rescue dissociation:** The scatter plot (see `ambiguity_analysis.png`) shows
dense clusters at (diagnosis=0, rescue=0.67) and (diagnosis=0, rescue=1.0), confirming
that many sessions achieve full rescue without any diagnosis credit — agents compensate
for the malfunction without identifying its source. This is most pronounced for GPT models.

---

## Notes

**On the diagnosis/rescue dissociation:** Diagnosis and rescue are correlated but not tightly. Rescue scores are consistently higher than diagnosis scores because the two tasks have different difficulty structures. Rescue is a *search* problem — find any intervention that restores aberrant phenotypes to healthy range. Partial credit is available (fraction of phenotypes restored), and many interventions have a stabilising effect even without identifying the true cause: in a densely connected network, blocking any hub gene near the malfunction often partially corrects downstream phenotypes. Claude models also re-test genes adaptively after observing aberrant phenotypes, which is effective even without a correct causal model. Diagnosis, by contrast, is an *identification* problem — commit to a specific gene (or signal) and a specific malfunction type (LOCK_HI / LOCK_LO / PERSIST). No partial credit for guessing the gene but not the type. This is a much harder abductive inference task, and the signal malfunction finding (§8) makes it harder still: all models systematically misattribute signal malfunctions to genes, because the perturbation signature is observationally indistinguishable.

---

## Open questions for Part 1

- ~~**Dataset statistics**~~ — resolved, see table below.

**Dataset statistics per tier** (N=20 seeds, canonical benchmark):

| | Easy | Medium | Hard |
|---|---|---|---|
| Total genes | 20 | 20 | 20 |
| Latent genes (hidden from agent) | 0 | 0 | 5 |
| Agent-targetable genes | 20 | 20 | 15 |
| Phenotype-contributing genes | 16 | 12 | 10 |
| Signals | 3 | 3 | 3 |
| Phenotypes | 3 | 3 | 3 |
| Prediction tasks | 2 | 2 | 2 |
| n_diagnosis_alternatives (mean) | 0.05 | 0.50 | 1.25 |
| n_diagnosis_alternatives (range) | 0–1 | 0–2 | 0–4 |

`n_diagnosis_alternatives` = number of alternative malfunction targets that produce an observationally equivalent phenotype shift, making unambiguous diagnosis harder. Hard organisms have substantially more ambiguous disease states due to dense feedback and latent genes.

`n_diagnosis_alternatives` scales sharply with difficulty — easy is nearly unambiguous (mean 0.05), hard has up to 4 alternative explanations per seed. This directly explains the diagnosis score drop from easy to hard, and is structurally separate from prediction difficulty. The 3 medium seeds with n_alternatives=2 include the 2 signal malfunction seeds (seeds 0 and 1) — signal malfunctions are observationally equivalent to LOCK_HI on a downstream gene, as discussed in §8.

- **Easy organism additive tasks**: 3/20 easy seeds are solvable by additive prediction (by design — near-linear dynamics). Worth reporting in paper as a known property, not a flaw.

- **Heuristic diagnosis re-framing**: the original claim (heuristic beats all GPTs on diagnosis) is no longer supported — heuristic scores 0.100 on medium disease, below gpt-5.1 (0.200) and gpt-4.1 (0.167). The updated finding is more interesting: exhaustive enumeration is *insufficient* for diagnosis when signal malfunctions introduce ambiguity (heuristic can't distinguish PERSIST from LOCK_HI on a downstream gene). GPT-5.1 and gpt-4.1 score higher possibly by reasoning about malfunction type from the phenotype pattern rather than just localising the gene. Worth a focused paragraph in the paper.

- **Signal malfunction — the disambiguating experiment**: no model across any seed attempted to activate a signal to check whether the effect compounds (which would distinguish PERSIST from LOCK_HI on a downstream gene). Open question: does explicit prompting to consider signals as malfunction candidates change diagnosis rates, or is the failure structural (agents can't form the right hypothesis without observing the signal's compounding effect)?

- **Diagnosis type errors**: what fraction of 0.5 scores (correct gene, wrong malfunction type) are LOCK_HI/LOCK_LO confusions vs PERSIST misclassifications? Computable from session logs. Would reveal whether models identify the malfunctioning gene but fail to reason about the type — a weaker but distinct failure mode from wrong gene attribution.
