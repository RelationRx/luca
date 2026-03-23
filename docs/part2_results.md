# Part 2 — Scaling Study Results

**Last updated:** 2026-03-23
**Design:** `docs/part2_plan.md`
**Models:** claude-sonnet-4-6, gpt-4o, heuristic, random
**Sweeps:** N=20, 40, 80, 160, 320, 640, 1280 — medium difficulty, healthy mode
**Seeds:** 10 per N for GPT-4o, heuristic, random; 10 for Sonnet N≤160, 5 for N≥320

---

## Scoring

**Task:** predict phenotype outcomes under novel two-gene interventions (healthy mode only).
**Metric:** prediction accuracy = fraction of phenotypes within ±0.10 of ground truth.
**Budget:** N + N_signals + 8 experiments per session.

---

## Results

### Composite scores (mean ± std)

| N | Budget | Sonnet | GPT-4o | Heuristic | Random | n (S/G/H/R) |
|---|--------|--------|--------|-----------|--------|-------------|
| 20 | 31 | 0.933±0.086 | 0.717±0.137 | 0.550±0.158 | 0.650±0.053 | 10/10/10/10 |
| 40 | 54 | 0.950±0.112 | 0.667±0.157 | 0.567±0.086 | 0.617±0.113 | 10/10/10/10 |
| 80 | 99 | 0.900±0.141 | 0.650±0.123 | 0.583±0.212 | 0.650±0.053 | 10/10/10/10 |
| 160 | 191 | 0.917±0.142 | 0.667±0.079 | 0.583±0.162 | 0.667±0.000 | 10/10/10/10 |
| 320 | 374 | 0.967±0.075 | 0.650±0.095 | 0.667±0.136 | 0.667±0.000 | 5/10/10/10 |
| 640 | 740 | 1.000±0.000 | 0.650±0.053 | 0.667±0.079 | 0.667±0.000 | 5/10/10/10 |
| 1280 | 1471 | 1.000±0.000 | 0.633±0.131 | 0.667±0.000 | 0.667±0.000 | 5/10/5/10 |

_Sonnet N≥320 and heuristic N=1280 have 5 seeds; full 10-seed runs pending._

---

## Analysis

### §1 Baseline performance

Both heuristic and random converge to 0.667 ± 0.000 at N≥160 and stay flat through N=1280.
This is a structural floor: all medium organisms have exactly 3 phenotypes, and the benchmark
prediction tasks involve two-gene cross-module interventions. The additive heuristic predicts
the sum of individual BLOCK effects — this approximation fails on the nonlinear sigmoid readout.
Predicting 0.5 everywhere lands 2/3 of phenotypes within ±0.10 by chance alone (since ≈2 of
3 outcomes fall in the mid-range), which is exactly what random achieves.

A striking finding: **random beats or ties heuristic at every N**. At N=20, random (0.650) >
heuristic (0.550). The heuristic's additive approximation actively misleads — structured search
with a wrong model is worse than no model at all. The crossover at N≥320 where heuristic
catches up to random (both 0.667) is because both are hitting the same floor, not because
the heuristic improves.

**Implication for RQ2**: heuristic failure is not N-dependent. The mechanism is the prediction
task design — cross-module double-gene interventions activate sigmoid nonlinearities that
additivity cannot represent. This is true at N=20 and N=1280 equally.

### §2 LLM vs baseline gap (RQ1)

Sonnet maintains high accuracy across all N, with scores ranging 0.900–1.000. At N≥640 it
achieves perfect 1.000 on all seeds. The Sonnet–heuristic gap is large throughout (0.283 at
N=20, widening to 0.333 at N=640), consistent with RQ1's hypothesis that LLM performance
holds or improves as N grows while the heuristic stays near-chance.

GPT-4o is a different story. Its score drops from 0.717 at N=20 to 0.633–0.667 for N≥40 —
essentially at the random baseline floor throughout. GPT-4o does not exhibit the LLM scaling
effect seen in Sonnet: it converges to chance at small N and stays there.

**RQ1 answer**: LLM scaling holds for Sonnet specifically, but is not a universal LLM
property — GPT-4o fails to outperform the random baseline at any N≥40. The cross-family
comparison reveals a sharp divergence.

### §3 Budget utilisation

| N | Budget | Sonnet used (%) | GPT-4o used (%) |
|---|--------|-----------------|-----------------|
| 20 | 31 | 81% | 44% |
| 40 | 54 | 78% | 28% |
| 80 | 99 | 79% | 14% |
| 160 | 191 | 74% | 8% |
| 320 | 374 | 50% | 3% |
| 640 | 740 | 24% | 2% |
| 1280 | 1471 | 13% | 1% |

Sonnet's budget usage drops with N but remains meaningful — it is allocating proportionally
less discovery time at large N but still running hundreds of experiments. GPT-4o undergoes a
**budget collapse**: at N=1280 it uses only 1% of its 1471-experiment budget (≈15 experiments)
before requesting prediction tasks. This is not context exhaustion — all sessions completed
normally — but a strategy failure where GPT-4o stops experimenting at scale.

Stall events (budget_used=0): Sonnet 0/70; GPT-4o 3/70 (one each at N=80, 320, 1280).
These are rare and not driving the score pattern.

### §4 Strategy analysis (RQ3)

From `analyse_strategy.py` on session logs.

#### Commitment timing (fraction of budget used before `get_next_prediction_task`)

| N | Sonnet commit | GPT-4o commit |
|---|---------------|---------------|
| 20 | 0.803±0.044 | 0.493±0.250 |
| 40 | 0.770±0.063 | 0.291±0.067 |
| 80 | 0.781±0.053 | 0.130±0.043 |
| 160 | 0.664±0.186 | 0.083±0.026 |
| 320 | 0.427±0.118 | 0.047±0.019 |
| 640 | 0.207±0.055 | 0.022±0.009 |
| 1280 | 0.094±0.039 | 0.010±0.005 |

Sonnet uses ~80% of budget before predicting at small N, dropping to ~9% at N=1280. This
reflects the budget collapse in absolute terms — Sonnet is running fewer total experiments
before pivoting to prediction tasks, but this is by necessity (80% of 31 = 25 experiments;
9% of 1471 = 132 experiments — Sonnet actually runs *more* experiments before predicting at
large N in absolute terms). The strategy is coherent: spend a roughly fixed number of
discovery experiments regardless of total budget, then switch to prediction.

GPT-4o's commitment fraction collapses to 1% at N=1280, consistent with ~15 experiments
total. It is committing to prediction after minimal discovery.

#### Intervention type mix

| N | Sonnet BLOCK | Sonnet BOOST | GPT-4o BLOCK | GPT-4o BOOST |
|---|--------------|--------------|--------------|--------------|
| 20 | 0.815±0.124 | 0.183±0.124 | 0.633±0.143 | 0.352±0.152 |
| 80 | 0.979±0.029 | 0.021±0.029 | 0.646±0.115 | 0.343±0.114 |
| 320 | 0.990±0.008 | 0.008±0.006 | 0.460±0.251 | 0.340±0.191 |
| 1280 | 0.994±0.003 | 0.004±0.003 | 0.521±0.036 | 0.462±0.058 |

Sonnet converges to near-exclusive BLOCK use at large N (99.4% at N=1280). BLOCK is the
most informative single intervention: it silences a gene and reveals all downstream
dependencies. As N grows and budget becomes the bottleneck, Sonnet drops the more targeted
BOOST/DAMPEN in favour of broad-coverage BLOCK. GPT-4o maintains a mixed BLOCK/BOOST
strategy throughout (~55/45), with no trend across N.

DAMPEN is near-zero for both models at all N (≤3%).

#### Redundancy (fraction of experiments re-perturbing an already-seen gene)

| N | Sonnet redundancy | GPT-4o redundancy |
|---|-------------------|-------------------|
| 20 | 0.458±0.124 | 0.458±0.212 |
| 80 | 0.296±0.184 | 0.338±0.174 |
| 320 | 0.404±0.096 | 0.433±0.272 |
| 1280 | 0.165±0.120 | 0.512±0.164 |

Both models start with ~45% redundancy at N=20. Sonnet's redundancy decreases at large N,
reaching 0.165 at N=1280 — it is becoming more selective as the search space grows. GPT-4o's
redundancy stays flat or increases, reaching 0.512 at N=1280. Given that GPT-4o only runs
~15 experiments at N=1280, ~50% redundancy means roughly half those are re-perturbations —
a highly inefficient strategy.

**RQ3 summary**: Sonnet adapts its strategy with N — near-exclusive BLOCK use, increasing
selectivity (decreasing redundancy), with absolute experiment count growing modestly before
prediction commitment. GPT-4o does not adapt: it commits to prediction after minimal
discovery regardless of N, maintains mixed interventions, and does not reduce redundancy.
This strategy gap likely explains the performance divergence.

---

## Open questions

- Sonnet N=1280 achieves perfect 1.000 — is this a ceiling effect? Would performance
  degrade with stricter thresholds (±0.08, ±0.07)? Computable post-hoc from logs.
- GPT-4o's flat ~0.650 from N=40 onwards: is this exactly 2/3 of phenotypes (structural
  floor) or slight variation? The std at N=40 is 0.157 — some sessions are scoring higher.
- Why does Sonnet's budget fraction drop so sharply at N≥320? Is it calling
  `get_next_prediction_task` earlier in absolute experiment count terms, or staying similar
  in absolute count? (The commitment fraction table is relative to budget, not absolute.)
- Sonnet N≥320 has only 5 seeds. Run the remaining 5 to confirm the 1.000 finding is robust.
- Heuristic N=1280 is at 5/10 seeds. Confirm once complete (does not affect conclusions).
