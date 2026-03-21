# LEMONOIDS Part 1 — Benchmark Validation Results

Technical reference for the Part 1 benchmark results. Stable as of 2026-03-21.
For chronological context and run notes see `experiments/paper_v1/LAB_JOURNAL.md`.

---

## Setup

**Models**: claude-opus-4-6, claude-sonnet-4-6, gpt-5.1, gpt-4o, gpt-4.1, heuristic, random (7 total)

**Sweeps**: 6 sweeps × 20 seeds × 7 models = **840 sessions**

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
| claude-opus-4-6 | **0.992** ± 0.036 | **0.900** ± 0.111 | **0.608** ± 0.192 |
| claude-sonnet-4-6 | 0.958 ± 0.089 | 0.875 ± 0.128 | 0.575 ± 0.250 |
| gpt-5.1 | 0.808 ± 0.142 | 0.781 ± 0.133 | 0.558 ± 0.206 |
| gpt-4o | 0.825 ± 0.123 | 0.667 ± 0.132 | 0.492 ± 0.201 |
| gpt-4.1 | 0.758 ± 0.134 | 0.667 ± 0.075 | 0.500 ± 0.253 |
| heuristic | 0.708 ± 0.089 | 0.575 ± 0.179 | 0.350 ± 0.196 |
| random | 0.667 ± 0.000 | 0.633 ± 0.085 | 0.350 ± 0.223 |

### Disease mode — composite score (mean ± std, N=20)

| Model | Easy | Medium | Hard |
|-------|------|--------|------|
| claude-opus-4-6 | **0.869** ± 0.169 | **0.794** ± 0.166 | **0.631** ± 0.182 |
| claude-sonnet-4-6 | 0.831 ± 0.163 | 0.733 ± 0.181 | 0.569 ± 0.217 |
| heuristic | 0.597 ± 0.183 | 0.531 ± 0.127 | 0.428 ± 0.209 |
| gpt-4o | 0.514 ± 0.105 | 0.464 ± 0.126 | 0.358 ± 0.191 |
| gpt-4.1 | 0.492 ± 0.256 | 0.456 ± 0.236 | 0.372 ± 0.293 |
| random | 0.481 ± 0.109 | 0.425 ± 0.131 | 0.278 ± 0.155 |
| gpt-5.1 | 0.344 ± 0.148 | 0.361 ± 0.232 | 0.178 ± 0.174 |

### Disease mode — breakdown by component (all tiers, N=20)

**Medium disease:**

| Model | Pred acc | Diagnosis | Rescue | Composite |
|-------|----------|-----------|--------|-----------|
| claude-opus-4-6 | 0.833 | **0.550** | 1.000 | **0.794** |
| claude-sonnet-4-6 | 0.867 | 0.350 | 0.983 | 0.733 |
| gpt-4.1 | 0.783 | 0.167 | 0.967 | 0.456 |
| heuristic | 0.608 | 0.100 | 0.883 | 0.531 |
| gpt-4o | 0.658 | 0.050 | 0.759 | 0.464 |
| random | 0.450 | 0.075 | 0.750 | 0.425 |
| gpt-5.1 | 0.700 | 0.200 | 0.810 | 0.361 |

**Easy disease:**

| Model | Pred acc | Diagnosis | Rescue | Composite |
|-------|----------|-----------|--------|-----------|
| claude-opus-4-6 | 0.958 | **0.650** | 1.000 | **0.869** |
| claude-sonnet-4-6 | 0.942 | 0.550 | 1.000 | 0.831 |
| heuristic | 0.692 | 0.250 | 0.850 | 0.597 |
| gpt-4.1 | 0.792 | 0.333 | 0.879 | 0.492 |
| random | 0.550 | 0.025 | 0.867 | 0.481 |
| gpt-4o | 0.717 | 0.075 | 0.750 | 0.514 |
| gpt-5.1 | 0.750 | 0.000 | 0.708 | 0.344 |

**Hard disease:**

| Model | Pred acc | Diagnosis | Rescue | Composite |
|-------|----------|-----------|--------|-----------|
| claude-opus-4-6 | 0.592 | **0.350** | 0.950 | **0.631** |
| claude-sonnet-4-6 | 0.542 | 0.300 | 0.867 | 0.569 |
| gpt-4.1 | 0.492 | 0.409 | 0.800 | 0.372 |
| heuristic | 0.450 | 0.200 | 0.633 | 0.428 |
| gpt-4o | 0.408 | 0.150 | 0.574 | 0.358 |
| random | 0.258 | 0.075 | 0.500 | 0.278 |
| gpt-5.1 | 0.392 | 0.214 | 0.333 | 0.178 |

---

## Analysis

### 1. Difficulty discriminates models cleanly

Easy is near-ceiling for Claude (0.96–0.99) but weaker for GPTs (0.76–0.83), making it a limited discriminator. Medium separates Claude from GPT clearly (Claude: 0.875–0.900; GPT: 0.667–0.781). Hard is the most discriminating tier: Claude Opus maintains 0.61, Sonnet 0.58, GPTs drop to 0.49–0.56. Both baselines collapse to 0.350 on hard — indistinguishable from chance — validating that hard organisms require genuine causal reasoning.

Degradation from easy to hard is gradual (no cliff) but with high per-seed variance on hard, indicating a bimodal structure: models either solve an organism or partially fail, not gracefully degrade within a seed.

| Model | Easy→Hard drop | Hard seeds ≥0.80 | Hard seeds <0.50 |
|-------|---------------|-----------------|-----------------|
| claude-opus-4-6 | −0.383 | 4/20 | 3/20 |
| claude-sonnet-4-6 | −0.383 | 6/20 | 6/20 |
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
| claude-sonnet-4-6 | 25.0 | 81% | 71.8% | 100% |
| gpt-5.1 | 26.6 | 85% | 64.8% | 56% |
| gpt-4o | 12.8 | 50% | 10.0% | 2% |
| gpt-4.1 | 16.8 | 63% | 5.0% | 3% |

Claude Opus runs a near-exhaustive single-gene BLOCK sweep covering all 20 genes. Claude Sonnet mixes single and multi-gene experiments but still achieves full coverage. GPT-5.1 runs many experiments but only covers 56% of genes (redundant). GPT-4o/4.1 run few experiments with near-zero systematic coverage.

Budget usage does not correlate with performance on hard (r ≈ 0.0–0.2): failures are early-stopping, not budget exhaustion.

In disease mode, Claude re-tests previously blocked genes after observing the aberrant phenotype (adaptive behaviour, 20/20 sessions). GPT models do this in 0–1/20 sessions.

**Budget usage across all six sweeps** (mean ± std, budget=31 for disease tiers):

| Model | Easy/H | Med/H | Hard/H | Med/D | Easy/D | Hard/D |
|-------|--------|-------|--------|-------|--------|--------|
| claude-opus-4-6 | — | 88% | — | 81% | 83% ± 5% | 82% ± 8% |
| claude-sonnet-4-6 | — | 81% | — | — | 78% ± 5% | 77% ± 6% |
| gpt-5.1 | — | 85% | — | 29% | 35% ± 25% | 30% ± 31% |
| gpt-4o | — | 50% | — | — | 26% ± 10% | 30% ± 17% |
| gpt-4.1 | — | 63% | — | — | 26% ± 21% | 32% ± 25% |
| heuristic | — | — | — | — | 68% ± 0% | 52% ± 1% |

Claude uses ~80% of budget consistently across all tiers and modes. GPT models use 26–35% on disease — context exhaustion truncates sessions early, explaining the disease score collapse. Heuristic drops on hard disease (52%) because fewer unambiguous candidates remain to enumerate once signal malfunctions and latent gene interactions are present.

**gpt-4.1 anomaly**: 11/20 disease seeds had zero experiments — the model read the organism description and submitted predictions and a hypothesis without any perturbation. This accidentally inflated its composite at ±0.15 (pred_acc from description alone can be high); at ±0.10 the anomaly disappears and gpt-4.1 correctly ranks below gpt-4o.

### 4. Prediction/diagnosis dissociation in GPT models

GPT models show a wide spread on medium disease diagnosis: gpt-4o near-chance (0.050), gpt-4.1 low (0.167), gpt-5.1 moderate (0.200) — despite reasonable prediction accuracy (0.66–0.78). Claude Opus leads diagnosis at 0.550, Claude Sonnet at 0.350. The heuristic scores 0.100, below gpt-5.1 and gpt-4.1 — exhaustive enumeration alone is insufficient when the malfunction signal is ambiguous.

This is a sharp dissociation: running perturbation experiments and accumulating evidence does not automatically translate to correct abductive inference in GPT models. Identifying the root cause of a phenotypic abnormality appears to require a qualitatively different reasoning capacity.

### 5. Diagnosis difficulty scales with organism complexity

Claude Opus diagnosis across difficulty tiers: 0.650 (easy) → 0.550 (medium) → 0.350 (hard). This is the cleanest signal of genuine reasoning difficulty in the benchmark — diagnosis requires forming a causal hypothesis about the malfunction, not just predicting steady-state outputs.

Rescue tracks diagnosis closely:
- Correct diagnosis (N=22 sessions): rescue fraction = 0.955
- Wrong diagnosis (N=78 sessions): rescue fraction = 0.526

Partial rescue even with wrong diagnosis reflects generic stabilising interventions that happen to restore some phenotypes — rescue fraction alone is a weak metric. Diagnosis score is the discriminating signal.

Diagnosis by ambiguity level (medium disease, N=100 sessions across Claude models):
- n_alternatives=0 (unambiguous, 74 sessions): Opus 62.5%, Sonnet 40%, GPTs 0–8%
- n_alternatives=1 (14 sessions): Opus 100%, Sonnet 50%, GPTs 0–33%
- n_alternatives≥2 (12 sessions): no model ever succeeds

### 6. Network reconstruction does not predict performance

Edge inference from perturbation experiments (mean over N=20 seeds, ground truth = 12.0 edges/organism):

**Medium healthy:**

| Model | Precision | Recall | F1 | Inferred edges |
|-------|-----------|--------|----|---------------|
| claude-opus-4-6 | 0.640 | **0.933** | **0.754** | 18.1 |
| claude-sonnet-4-6 | 0.675 | 0.775 | 0.710 | 14.1 |
| gpt-5.1 | 0.570 | 0.754 | 0.644 | 15.3 |
| gpt-4o | 0.325 | 0.246 | 0.270 | 5.8 |
| gpt-4.1 | 0.153 | 0.112 | 0.109 | 3.0 |

**Hard healthy:**

| Model | Precision | Recall | F1 | Inferred edges |
|-------|-----------|--------|----|---------------|
| claude-opus-4-6 | 0.265 | **0.752** | 0.390 | 34.0 |
| claude-sonnet-4-6 | 0.277 | 0.675 | 0.390 | 30.0 |
| gpt-5.1 | 0.257 | 0.719 | 0.376 | 30.7 |
| gpt-4o | 0.128 | 0.205 | 0.153 | 10.1 |
| gpt-4.1 | 0.227 | 0.441 | 0.294 | 20.1 |

Edges are `(gene, phenotype, direction)` triples inferred from observed phenotype shifts >0.05 on single-gene BLOCK/BOOST experiments.

On medium, Claude Opus achieves high recall (0.933) by over-inferring edges (18.1 inferred vs 12.0 ground truth), trading precision for coverage. On hard, precision collapses across all models — dense feedback and latent genes make phenotype shifts ambiguous, leading to many false positive edges (Opus: 34.0 inferred vs 12.2 ground truth). gpt-4o/4.1 run fewer experiments and infer fewer edges, explaining their low recall.

**Correlation with prediction accuracy** (Pearson r):

| Model | Medium r | Hard r |
|-------|----------|--------|
| claude-opus-4-6 | −0.30 | +0.18 |
| claude-sonnet-4-6 | +0.09 | +0.26 |
| gpt-5.1 | +0.01 | −0.02 |
| gpt-4o | −0.16 | +0.02 |
| gpt-4.1 | +0.21 | +0.46 |

Correlations are weak and inconsistent — higher network F1 does not reliably predict better prediction accuracy. Opus has a negative r on medium despite the highest F1, suggesting its prediction performance draws on something beyond explicit edge reconstruction. Note: this metric only captures gene→phenotype edges; gene→gene regulatory edges are not recoverable from current logs (see Ideas).

### 7. Hypothesis quality (disease mode, qualitative)

| Model | Text present | Avg length | Cites evidence |
|-------|-------------|------------|----------------|
| claude-opus-4-6 | 20/20 | 1292 chars | 19/20 |
| claude-sonnet-4-6 | 20/20 | 1336 chars | 19/20 |
| gpt-5.1 | 19/20 | **2932 chars** | 19/19 |
| gpt-4.1 | 20/20 | 799 chars | 13/20 |
| gpt-4o | 17/20 | 429 chars | 6/17 |

Claude hypotheses are concise, cite specific experiment results (e.g. "BLOCK G013 → signal-output = 0.77"), and identify gene, malfunction type, and mechanism. Even wrong Claude hypotheses are well-reasoned — they identify plausible alternatives with real evidence.

GPT-5.1 writes the longest hypotheses (2932 chars avg) but its one correct diagnosis came with no free text; wrong cases are verbose, fluent, and evidence-rich but reason toward wrong conclusions. GPT-4o produces the shortest hypotheses, rarely cites evidence.

### 8. Gene attribution bias — signal malfunctions never diagnosed

Two medium disease seeds (0 and 1) have signal malfunctions (thermal-pulse PERSIST, coupling-factor-Q PERSIST). No model across any seed correctly diagnosed a signal malfunction. Both Claude models identified compensating gene targets (correct rescue, wrong cause). GPT-4o was the only model to name a signal at all (wrong signal). GPT-5.1/4.1 submitted nothing valid.

Models systematically frame malfunctions as gene-level even when the true cause is an external signal. The `n_diagnosis_alternatives` metric correctly flagged both seeds (value=2), validating the ambiguity measure — the signal malfunction is observationally indistinguishable from a specific gene malfunction from the agent's vantage point.

This is not a prompt artefact. The system prompt and `submit_malfunction_hypothesis` tool definition both explicitly list signals as candidates alongside genes, and PERSIST is described as a distinct malfunction type. The bias is structural: a persistently active signal produces the same perturbation signature as a LOCK_HI on its most downstream gene target, because agents can activate signals but cannot block them. The only disambiguating experiment would be to *activate* the signal and observe whether the effect compounds — but no model across any seed attempted this. This represents an intentional source of diagnostic difficulty in the benchmark design, not a flaw, and `n_diagnosis_alternatives` correctly identifies it.

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
