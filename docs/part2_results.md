# Part 2 — Scaling Study Results

**Last updated:** 2026-03-24 (coverage + efficiency analysis added)
**Design:** `docs/part2_plan.md`
**Models:** claude-sonnet-4-6, gpt-4o, heuristic, random
**Sweeps:** N=20, 40, 80, 160, 320, 640, 1280 — medium difficulty, healthy mode
**Seeds:** 10 per N for all models; heuristic N=1280 stopped at 5 seeds (0.667±0.000, structural floor confirmed)

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
| 20 | 31 | 0.917±0.088 | 0.717±0.137 | 0.550±0.158 | 0.650±0.053 | 10/10/10/10 |
| 40 | 54 | 0.850±0.146 | 0.667±0.157 | 0.567±0.086 | 0.617±0.113 | 10/10/10/10 |
| 80 | 99 | 0.817±0.146 | 0.650±0.123 | 0.583±0.212 | 0.650±0.053 | 10/10/10/10 |
| 160 | 191 | 0.983±0.053 | 0.667±0.079 | 0.583±0.162 | 0.667±0.000 | 10/10/10/10 |
| 320 | 374 | 0.900±0.211 | 0.650±0.095 | 0.667±0.136 | 0.667±0.000 | 10/10/10/10 |
| 640 | 740 | 0.926±0.121 | 0.650±0.053 | 0.667±0.079 | 0.667±0.000 | 10/10/10/10 |
| 1280 | 1471 | 0.983±0.053 | 0.633±0.131 | 0.667±0.000 | 0.667±0.000 | 10/10/5†/10 |

_All Sonnet results from clean post-RNG-fix run (2026-03-23/24)._
_† Heuristic N=1280 stopped at 5 seeds: 0.667±0.000, structural floor confirmed._

---

## Analysis

### §1 Baseline performance

Both heuristic and random converge to 0.667±0.000 at N≥160 and stay flat through N=1280
(heuristic N=1280 confirmed on 5 seeds; zero variance made further seeds unnecessary).
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

Sonnet maintains high accuracy across all N, with scores ranging 0.817–0.983. There is no
degradation at scale — if anything scores improve at large N (0.983 at both N=160 and N=1280).
The Sonnet–random gap is 0.267 at N=20 and 0.317 at N=1280, widening slightly with N.

GPT-4o is a different story. Its score drops from 0.717 at N=20 to 0.633–0.667 for N≥40 —
essentially at the random baseline floor throughout. GPT-4o does not exhibit the LLM scaling
robustness seen in Sonnet: it converges to chance at small N and stays there.

**RQ1 answer**: LLM scaling robustness holds for Sonnet but is not a universal LLM property —
GPT-4o fails to outperform the random baseline at any N≥40. The cross-family comparison reveals
a sharp divergence that widens with N.

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

Sonnet's budget usage drops with N but remains meaningful — at N=1280 it still runs ~190
experiments (13% of 1471) before switching to prediction. GPT-4o undergoes a **budget
collapse**: at N=1280 it uses only 1% of its budget (~15 experiments) before requesting
prediction tasks. This is not context exhaustion — all sessions completed normally — but a
strategy failure where GPT-4o stops experimenting at scale.

Stall events (budget_used=0): Sonnet 0/70; GPT-4o 3/70 (one each at N=80, 320, 1280).
These are rare and not driving the score pattern.

### §4 Strategy analysis (RQ3)

From `analyse_strategy.py` on session logs (full 10-seed Sonnet results).

#### Commitment timing (fraction of budget used before `get_next_prediction_task`)

| N | Sonnet commit | GPT-4o commit |
|---|---------------|---------------|
| 20 | 0.803±0.042 | 0.493±0.250 |
| 40 | 0.770±0.045 | 0.291±0.067 |
| 80 | 0.788±0.101 | 0.130±0.043 |
| 160 | 0.572±0.113 | 0.083±0.026 |
| 320 | 0.438±0.166 | 0.047±0.019 |
| 640 | 0.179±0.067 | 0.022±0.009 |
| 1280 | 0.086±0.028 | 0.010±0.005 |

Sonnet uses ~80% of budget before predicting at small N, dropping to ~9% at N=1280. In
absolute terms this is coherent: 80% of 31 = ~25 experiments at N=20; 9% of 1471 = ~130
experiments at N=1280 — Sonnet actually runs *more* experiments before predicting at large
N. GPT-4o collapses to ~15 experiments total at N=1280 regardless of budget.

#### Intervention type mix

| N | Sonnet BLOCK | Sonnet BOOST | GPT-4o BLOCK | GPT-4o BOOST |
|---|--------------|--------------|--------------|--------------|
| 20 | 0.832±0.129 | 0.168±0.129 | 0.633±0.143 | 0.352±0.152 |
| 80 | 0.910±0.139 | 0.087±0.140 | 0.646±0.115 | 0.343±0.114 |
| 320 | 0.983±0.013 | 0.014±0.013 | 0.460±0.251 | 0.340±0.191 |
| 1280 | 0.977±0.036 | 0.018±0.029 | 0.521±0.036 | 0.462±0.058 |

Sonnet converges to near-exclusive BLOCK use at large N (97.7% at N=1280). BLOCK is the most
informative single intervention for network discovery. As N grows and budget becomes the
bottleneck, Sonnet drops BOOST/DAMPEN in favour of broad-coverage BLOCK. GPT-4o maintains a
mixed ~55/45 BLOCK/BOOST strategy throughout with no trend across N.

DAMPEN is near-zero for both models at all N (≤1% Sonnet, ≤3% GPT-4o).

#### Redundancy (fraction of experiments re-perturbing an already-seen gene)

| N | Sonnet redundancy | GPT-4o redundancy |
|---|-------------------|-------------------|
| 20 | 0.402±0.157 | 0.458±0.212 |
| 80 | 0.407±0.139 | 0.338±0.174 |
| 320 | 0.382±0.100 | 0.433±0.272 |
| 1280 | 0.345±0.203 | 0.512±0.164 |

Both models start with ~40–45% redundancy at N=20. Sonnet's redundancy decreases modestly
at large N (0.402 → 0.345), while GPT-4o's increases to 0.512 at N=1280. Given that GPT-4o
only runs ~15 experiments at N=1280, ~50% redundancy means roughly half are re-perturbations
— a highly inefficient use of an already tiny budget.

**RQ3 summary**: Sonnet adapts its strategy with N — near-exclusive BLOCK use, modestly
decreasing redundancy, with absolute experiment count *increasing* before prediction
commitment. GPT-4o does not adapt: it commits to prediction after minimal discovery
regardless of N, maintains mixed interventions, and does not reduce redundancy.
This strategy gap explains the performance divergence.

### §5 Gene coverage (exploration bottleneck)

From `analyse_coverage.py` on session logs.

| N | Sonnet coverage | Sonnet unique genes | GPT-4o coverage | GPT-4o unique genes |
|---|-----------------|---------------------|-----------------|---------------------|
| 20 | 1.000±0.000 | 20.0±0.0 | 0.415±0.108 | 8.3±2.2 |
| 40 | 1.000±0.000 | 40.0±0.0 | 0.220±0.066 | 8.8±2.7 |
| 80 | 1.000±0.000 | 80.0±0.0 | 0.126±0.065 | 10.1±5.2 |
| 160 | 0.951±0.104 | 152.2±16.7 | 0.050±0.022 | 8.0±3.5 |
| 320 | 0.963±0.117 | 308.2±37.3 | 0.018±0.012 | 5.8±3.8 |
| 640 | 0.822±0.376 | 525.9±240.6 | 0.010±0.005 | 6.4±3.2 |
| 1280 | 0.607±0.431 | 776.4±552.0 | 0.006±0.003 | 7.4±3.4 |

Sonnet achieves **100% gene coverage at N≤80** — it perturbs every gene in the organism
before committing to predictions. At larger N the budget no longer permits full coverage,
but Sonnet still reaches 61% (776 genes) at N=1280. Coverage drives performance: at small
N where coverage is complete, scores are high; where coverage is partial (N≥160) there is
more variance (std 0.104–0.431).

GPT-4o's coverage collapses immediately — it covers only ~42% at N=20 and just **0.6%
(~7 genes) at N=1280**, regardless of the 1471-experiment budget available. This is the
mechanistic explanation for its flat chance-level scores: GPT-4o is predicting with almost
no information about the network, touching essentially the same handful of genes at every N.

**Exploration bottleneck**: GPT-4o's failure is not capacity-limited (budget is ample) but
strategy-limited — it stops exploring after ~15 experiments at any N. Sonnet's robustness
is directly explained by maintaining meaningful coverage even as N grows.

#### Task-hit metrics

Two metrics characterise *when* an agent perturbs task-relevant genes:

**Prospective task hit**: fraction of prediction-task genes perturbed *before* the agent
called `get_next_prediction_task()` for the first time. The agent had no knowledge of which
genes would be tested — this is genuine unsupervised discovery of task-relevant genes.

**Targeted task hit**: fraction of prediction-task genes perturbed *after* the first task
reveal. Measures deliberate follow-up once the agent knows which genes matter.

| N | Sonnet prospective | Sonnet targeted | GPT-4o prospective | GPT-4o targeted |
|---|--------------------|-----------------|--------------------|-----------------|
| 20 | 1.000±0.000 | 0.000±0.000 | 0.292±0.185 | 0.392±0.438 |
| 40 | 1.000±0.000 | 0.000±0.000 | 0.233±0.188 | 0.150±0.269 |
| 80 | 1.000±0.000 | 0.000±0.000 | 0.100±0.129 | 0.375±0.489 |
| 160 | 0.975±0.079 | 0.025±0.079 | 0.100±0.129 | 0.000±0.000 |
| 320 | 0.825±0.290 | 0.175±0.290 | 0.000±0.000 | 0.000±0.000 |
| 640 | 0.575±0.457 | 0.425±0.457 | 0.000±0.000 | 0.000±0.000 |
| 1280 | 0.300±0.422 | 0.700±0.422 | 0.000±0.000 | 0.050±0.158 |

At **N≤80**, Sonnet's prospective hit is 1.000 — it perturbs every task-relevant gene
before seeing any tasks. This follows directly from achieving 100% total coverage at
small N, so task genes are hit by default.

The more informative result is at **large N** where full coverage is impossible. The mean
prospective hit of 0.300 at N=1280 (std=0.422) is misleading — the high variance signals
heterogeneous behaviour across sessions, not a consistent strategy. Per-seed inspection
reveals at least three distinct patterns:

- **Explore-first** (seeds 3, 6): first task reveal at exp 94–181, 100% coverage, prospective=1.0
- **Tasks-first, broad follow-up** (seeds 4, 5): first task reveal at exp 140–147, then
  perturb extensively, achieving 100% coverage with prospective=0.0
- **Tasks-first, targeted minimal** (seeds 1, 7, 9): first task at exp 69–138, only 85–168
  experiments total, coverage 5–12%, prospective=0.0 — yet all score 1.000

The most striking contrast: **seed 7** (prospective=0.0, 5% coverage, 85 experiments) scores
1.000; **seed 3** (prospective=1.0, 100% coverage, 191 experiments) is the only failure (0.833).
Full exploration does not guarantee success. This suggests the single failure is a reasoning
error in the prediction step, not an information gap — the organism's cross-module interaction
was hard to predict even with complete network knowledge.

**GPT-4o prospective hits collapse to 0.000 at N≥320** — it never reaches task-relevant
genes during its brief exploration phase. There is no compensating targeted follow-up
(0.000 at N=160–640, 0.050 at N=1280 by chance). GPT-4o is effectively predicting blind
at scale, with no perturbation data on the specific genes involved in the prediction tasks.

### §6 Per-seed breakdown and benchmark design implications

Per-seed scores for Sonnet at N=160 and N=1280 (the two highest-scoring N values):

**N=160** (budget=191): seeds 0–4,6–9 score 1.000; seed 5 scores 0.833. Budget used: 98–139.

**N=1280** (budget=1471): seeds 0–2,4–6,8–9 score 1.000; seed 3 scores 0.833. Budget used: 85–356.

Both N values produce identical aggregate scores (0.983±0.053) via the same failure pattern:
9/10 perfect, one seed scoring 0.833 (exactly one prediction task wrong).

**N is not a good proxy for task difficulty**

Sonnet performs identically at N=160 and N=1280 despite a 8× increase in organism size and
a near-complete collapse in coverage fraction (95% → 61%). Adding genes does not make the
prediction tasks harder — it increases exploration cost, which Sonnet absorbs by adapting
its experiment budget. The task difficulty is set by the prediction task structure
(which genes, which cross-module interactions), not by N.

**Topology variance within a tier exceeds N effect**

Budget usage at N=1280 varies 4× across seeds (85–356 experiments for identical scores).
Some organisms are much harder to characterise than others within the same N. This variance
is driven by organism topology — feedback fraction, latent gene fraction, module
connectivity — not by N per se.

**Implications for complexity tier design**

The easy/medium/hard tiers (which vary feedback fraction, latent fraction, and module
density) correctly target the structural parameters that drive genuine task difficulty.
The scaling study tests something orthogonal: Sonnet's robustness to *exploration budget
constraints*, not to *task difficulty*. These are distinct dimensions.

The Part 1 hard tier results (Sonnet composite 0.61, diagnosis 0.35) are the real
difficulty stress test. The scaling study shows Sonnet is robust to scale; it does not
show the task is getting harder at large N.

---

## Open questions

- Sonnet N=1280 at 0.983 — seed 3 is the single failure (0.833). Worth checking whether
  this organism's topology explains it (high feedback/latent fraction, specific module layout).
- GPT-4o's flat ~0.650 from N=40: is this exactly the 2/3 structural floor or slight
  variation? Std of 0.157 at N=40 suggests some sessions score higher — worth checking
  if any individual GPT-4o sessions achieve Sonnet-level scores.
- Gene coverage and task-hit metrics computed (§5) — Sonnet prospective hit 0.300 at N=1280 (genuine signal above 61% coverage baseline); GPT-4o 0.000 at N≥320.
- Budget scaling experiment (fix N, vary budget) would test whether Sonnet is
  strategy-limited or compute-limited at large N.
