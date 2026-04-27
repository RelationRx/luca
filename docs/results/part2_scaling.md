# Part 2 — Scaling Study Results

**Last updated:** 2026-04-17 (CausalSweep baseline added)
**Design:** `docs/designs/part2_scaling_plan.md`
**Models:** claude-sonnet-4-6, deepseek-v3 (DeepSeek V3.1), qwen-3.5 (Qwen 3.5 397B), gpt-4o, causal-sweep, heuristic, random
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

| N | Budget | CausalSweep | Sonnet | DeepSeek V3.1 | Qwen 3.5 | GPT-4o | Heuristic | Random |
|---|--------|-------------|--------|---------------|----------|--------|-----------|--------|
| 20 | 31 | **0.983**±0.050 | 0.917±0.083 | 0.917±0.083 | 0.917±0.083 | 0.717±0.130 | 0.550±0.150 | 0.650±0.050 |
| 40 | 54 | **0.950**±0.076 | 0.850±0.138 | 0.850±0.203 | 0.926±0.083 | 0.667±0.149 | 0.567±0.082 | 0.617±0.107 |
| 80 | 99 | 0.883±0.150 | 0.817±0.138 | **0.883**±0.107 | 0.717±0.198 | 0.650±0.117 | 0.583±0.201 | 0.650±0.050 |
| 160 | 191 | 0.933±0.082 | **0.983**±0.050 | 0.933±0.111 | 0.900±0.111 | 0.667±0.075 | 0.583±0.154 | 0.667±0.000 |
| 320 | 374 | 0.800±0.145 | **0.900**±0.200 | 0.850±0.117 | 0.800±0.100 | 0.650±0.090 | 0.667±0.129 | 0.667±0.000 |
| 640 | 739 | 0.883±0.107 | **0.926**±0.114 | 0.917±0.112 | 0.817±0.138 | 0.650±0.050 | 0.667±0.075 | 0.667±0.000 |
| 1280 | 1471 | 0.800±0.125 | **0.983**±0.050 | 0.817±0.138 | 0.783±0.150 | 0.633±0.125 | 0.667±0.000 | 0.667±0.000 |

Best per column in bold. N=10 seeds per cell except Sonnet N=640 (9) and heuristic N=1280 (5†).

_† Heuristic N=1280 stopped at 5 seeds: 0.667±0.000, structural floor confirmed._

---

## Analysis

### §1 Baseline performance

Random reaches the structural floor of 0.667±0.000 at N≥160; heuristic reaches the same
floor at N≥320 (still 0.583±0.154 at N=160). Both stay flat through N=1280 (heuristic
N=1280 confirmed on 5 seeds; zero variance made further seeds unnecessary).

#### Why the floor is exactly 2/3

Random predicts 0.5 for every phenotype regardless of intervention. With the ±0.10
accuracy threshold, scoring correct on a phenotype requires the post-intervention value
to land in [0.4, 0.6]. The 2/3 floor follows from the construction of LUCA prediction
tasks (`luca/experiment.py:_generate_tasks`):

1. **Two genes are sampled from a single phenotype's readout dependencies** (preferring
   shared-readout pairs to ensure non-additivity through the sigmoid). Each receives a
   {BLOCK, BOOST, DAMPEN} intervention.
2. **Non-triviality retry**: the pair is re-sampled up to 20 times until at least one
   phenotype shifts by ≥ 0.10 from baseline (`min_shift = 0.1`). This guarantees ≥1 of
   the 3 phenotypes is pushed outside [0.4, 0.6] — random cannot trivially score 1.0.
3. **Cross-module structure** (inter-module edge density 0.04 / 0.08 / 0.15 across
   easy/medium/hard tiers; see `benchmark_design.md` §3) means the two perturbed genes
   feeding into one phenotype's readout typically leave the other two phenotypes near
   their baseline value. The readout bias is constructed so σ(0) = 0.5 at baseline.

Per-task expected accuracy:

```
acc_random = #{phenotypes still in [0.4, 0.6]} / 3 ≈ 2 / 3 = 0.667
```

The floor is *exact* at N≥160: random scores 0.667±0.000, meaning every task lands
precisely 1 phenotype outside the band and 2 inside. At small N (≤80), occasional
spillover from the perturbed genes to a second phenotype lowers the score (e.g.
0.650±0.050 at N=20). As N grows, cross-module structure becomes more strict relative
to intra-module density, the perturbed genes' effect concentrates on the single
shared-readout phenotype, and the floor becomes a perfect attractor.

#### Why heuristic doesn't simply hit 2/3 at small N

Heuristic does not hit the same floor by accident. It actively misleads on shared-readout
2-gene perturbations: the additive single-gene approximation fails through the sigmoid
nonlinearity, predicting effects that compound when in reality they saturate. At N=20
this drives heuristic to 0.550 — *below* random's 0.650.

A striking finding: **random beats or ties heuristic at every N**. The crossover at N≥320
where both converge to 0.667 is not because the heuristic improves; it is because most
phenotypes are structurally unaffected by the intervention at large N, so the additive
model's misspecification on the one affected phenotype is amortised away. Both methods
end up landing in the same 2-of-3-phenotypes-near-baseline regime.

**Implication for RQ2**: heuristic failure is not N-dependent. The mechanism is the
prediction task design — cross-module double-gene interventions activate sigmoid
nonlinearities that additivity cannot represent. This is true at N=20 and N=1280 equally.

### §2 Scaling behaviour (RQ1)

**CausalSweep** leads at small N (0.983 at N=20) but degrades to 0.800 at N=1280. The crossover with Sonnet occurs at N≈160: below this, rule-based logit-space prediction with full gene coverage wins; above it, LLM reasoning with adaptive exploration wins.

Three LLMs maintain high accuracy across all N with no degradation at scale:
- **Sonnet**: 0.817–0.983, widening gap over CausalSweep with N
- **DeepSeek V3.1**: 0.850–0.933, competitive with Sonnet through N=640, modest decline at N=1280 (0.817)
- **Qwen 3.5**: 0.717–0.926, competitive at small N, gradual decline at large N (0.783 at N=1280)

GPT-4o drops from 0.717 at N=20 to 0.633–0.667 for N≥40 — essentially at the random baseline floor throughout.

**RQ1 answer**: LLM scaling robustness holds for Sonnet and both open-source models but is not a universal LLM property. The CausalSweep crossover at N≈160 shows that LLMs' advantage at scale comes from adaptive exploration strategy, not from better mathematical modelling — CausalSweep already has the optimal prediction formula.

### §3 Budget utilisation

| N | Budget | CausalSweep | Sonnet | DeepSeek V3.1 | Qwen 3.5 | GPT-4o |
|---|--------|-------------|--------|---------------|----------|--------|
| 20 | 31 | 100% ± 0% | 81% ± 4% | 82% ± 6% | 89% ± 7% | 44% ± 20% |
| 40 | 54 | 100% ± 0% | 78% ± 4% | 58% ± 13% | 84% ± 8% | 28% ± 11% |
| 80 | 99 | 100% ± 0% | 81% ± 7% | 28% ± 4% | 63% ± 15% | 14% ± 6% |
| 160 | 191 | 100% ± 0% | 63% ± 7% | 17% ± 3% | 35% ± 12% | 8% ± 2% |
| 320 | 374 | 100% ± 0% | 60% ± 19% | 9% ± 1% | 18% ± 4% | 3% ± 2% |
| 640 | 739 | 100% ± 0% | 39% ± 24% | 5% ± 1% | 8% ± 1% | 2% ± 1% |
| 1280 | 1471 | 100% ± 0% | 15% ± 6% | 2% ± 1% | 4% ± 1% | 1% ± 0% |

Budget usage patterns across N:
- **CausalSweep**: 100% at every N (deterministic: BLOCK all N genes + BOOST remainder). This is the maximum possible budget usage.
- **Sonnet**: gradual decline (81% → 15%), still running ~224 experiments at N=1280. High variance at intermediate N (std=24% at N=640) reflects bimodal strategy.
- **DeepSeek V3.1**: steep drop (82% → 2%), running ~35 experiments at N=1280 — yet scores 0.817. Low variance throughout (std=1–13%), indicating a consistent strategy.
- **Qwen 3.5**: moderate drop (89% → 4%), running ~62 experiments at N=1280. Moderate variance (std=1–15%).
- **GPT-4o**: collapses to 1% by N=1280 (~13 experiments), at baseline floor. High variance at small N (std=20% at N=20), near-zero at large N.

The most striking finding: **DeepSeek achieves 0.917 at N=640 with only 5% budget usage (~34 experiments)** while Sonnet uses 39% (~286 experiments) for 0.926. DeepSeek's per-experiment efficiency is far higher, though Sonnet's more thorough exploration leads at the largest scales.

### §4 Strategy analysis (RQ3)

From `analyse_strategy.py` on session logs (full 10-seed Sonnet results).

#### Commitment timing (fraction of budget used before `get_next_prediction_task`)

| N | CausalSweep | Sonnet | DeepSeek V3.1 | Qwen 3.5 | GPT-4o |
|---|-------------|--------|---------------|----------|--------|
| 20 | 1.000±0.000 | 0.803±0.042 | 0.735±0.077 | 0.890±0.072 | 0.493±0.250 |
| 40 | 1.000±0.000 | 0.770±0.045 | 0.419±0.073 | 0.835±0.083 | 0.291±0.067 |
| 80 | 1.000±0.000 | 0.788±0.101 | 0.195±0.031 | 0.617±0.159 | 0.130±0.043 |
| 160 | 1.000±0.000 | 0.572±0.113 | 0.109±0.021 | 0.325±0.121 | 0.083±0.026 |
| 320 | 1.000±0.000 | 0.438±0.166 | 0.056±0.007 | 0.163±0.038 | 0.047±0.019 |
| 640 | 1.000±0.000 | 0.179±0.067 | 0.032±0.013 | 0.077±0.012 | 0.022±0.009 |
| 1280 | 1.000±0.000 | 0.086±0.028 | 0.015±0.004 | 0.039±0.014 | 0.010±0.005 |

CausalSweep always uses 100% of budget before predicting (deterministic BLOCK+BOOST sweep). The fraction drops for all LLMs because the budget grows as O(N) while absolute experiment counts grow sublinearly. In absolute terms (experiments before predicting):

| N | Budget | CausalSweep | Sonnet | DeepSeek | Qwen | GPT-4o |
|---|--------|-------------|--------|----------|------|--------|
| 20 | 31 | 31 | ~25 | ~23 | ~28 | ~15 |
| 80 | 99 | 99 | ~78 | ~19 | ~61 | ~13 |
| 320 | 374 | 374 | ~164 | ~21 | ~61 | ~18 |
| 1280 | 1471 | 1471 | ~130 | ~22 | ~57 | ~15 |

CausalSweep always exhausts the budget — yet its scores degrade at large N (0.983 → 0.800) because the symmetric BOOST fallback accumulates errors for genes it couldn't BOOST. Sonnet runs fewer experiments (130 at N=1280) but scores higher (0.983) because it reasons from partial data rather than relying on a fallback formula. DeepSeek runs ~20 regardless of N — the most parsimonious strategy. GPT-4o also runs ~15 but achieves only baseline-level scores — the difference is experiment quality, not quantity.

#### Intervention type mix (BLOCK fraction)

| N | CausalSweep | Sonnet | DeepSeek V3.1 | Qwen 3.5 | GPT-4o |
|---|-------------|--------|---------------|----------|--------|
| 20 | 0.645 | 0.832 | 0.555 | 0.628 | 0.633 |
| 80 | 0.808 | 0.910 | 0.506 | 0.801 | 0.646 |
| 320 | 0.855 | 0.983 | 0.533 | 0.718 | 0.460 |
| 1280 | 0.977 | 0.519 | 0.637 | 0.521 |

Sonnet converges to near-exclusive BLOCK use at large N (97.7% at N=1280) — BLOCK is the most informative single intervention for network discovery. Qwen trends toward BLOCK (63–80%) but less exclusively. DeepSeek and GPT-4o both maintain a mixed ~50/50 BLOCK/BOOST strategy with no trend across N — but DeepSeek achieves far better scores with this mix. DAMPEN is near-zero for all models at all N.

#### Redundancy (fraction of experiments re-perturbing an already-seen gene)

| N | CausalSweep | Sonnet | DeepSeek V3.1 | Qwen 3.5 | GPT-4o |
|---|-------------|--------|---------------|----------|--------|
| 20 | 0.355 | 0.402 | 0.441 | 0.372 | 0.458 |
| 80 | 0.192 | 0.407 | 0.498 | 0.223 | 0.338 |
| 320 | 0.144 | 0.382 | 0.473 | 0.390 | 0.433 |
| 1280 | 0.130 | 0.345 | 0.476 | 0.485 | 0.512 |

CausalSweep has the lowest redundancy at large N (0.130 at N=1280) because it BLOCKs each gene exactly once, then BOOSTs high-priority genes once — no gene is perturbed more than twice. Redundancy decreases with N because the BOOST phase covers a shrinking fraction of genes. DeepSeek has consistently high redundancy (~47–50%) — with only ~20 experiments, nearly half re-perturb genes it has already seen. Sonnet's redundancy decreases modestly at large N (0.402 → 0.345). GPT-4o's increases to 0.512 at N=1280 — but unlike DeepSeek, the redundancy does not translate to better scores.

**RQ3 summary**: Sonnet adapts its strategy with N — near-exclusive BLOCK use, modestly
decreasing redundancy, with absolute experiment count *increasing* before prediction
commitment. GPT-4o does not adapt: it commits to prediction after minimal discovery
regardless of N, maintains mixed interventions, and does not reduce redundancy.
DeepSeek and Qwen represent a third pattern: low budget usage with high per-experiment
efficiency (see §5). DeepSeek in particular achieves near-Sonnet scores with 5–10× fewer
experiments, suggesting it selects high-information targets rather than sweeping broadly.

### §5 Gene coverage (exploration bottleneck)

From `analyse_coverage.py` on session logs.

| N | CausalSweep cov | CausalSweep genes | Sonnet coverage | Sonnet genes | DeepSeek coverage | DeepSeek genes | Qwen coverage | Qwen genes | GPT-4o coverage | GPT-4o genes |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 1.000 ± 0.000 | 20 | 1.000 ± 0.000 | 20.0 | 0.685 ± 0.160 | 13.7 | 0.855 ± 0.149 | 17.1 | 0.415 ± 0.103 | 8.3 |
| 40 | 1.000 ± 0.000 | 40 | 1.000 ± 0.000 | 40.0 | 0.362 ± 0.099 | 14.5 | 0.882 ± 0.149 | 35.3 | 0.220 ± 0.063 | 8.8 |
| 80 | 1.000 ± 0.000 | 80 | 1.000 ± 0.000 | 80.0 | 0.171 ± 0.029 | 13.7 | 0.665 ± 0.216 | 53.2 | 0.126 ± 0.062 | 10.1 |
| 160 | 1.000 ± 0.000 | 160 | 0.951 ± 0.099 | 152.2 | 0.104 ± 0.025 | 16.7 | 0.261 ± 0.119 | 41.8 | 0.056 ± 0.013 | 9.0 |
| 320 | 1.000 ± 0.000 | 320 | 0.963 ± 0.111 | 308.2 | 0.053 ± 0.013 | 16.8 | 0.141 ± 0.046 | 45.1 | 0.024 ± 0.010 | 7.8 |
| 640 | 1.000 ± 0.000 | 640 | 0.822 ± 0.357 | 525.9 | 0.025 ± 0.005 | 15.9 | 0.068 ± 0.020 | 43.2 | 0.011 ± 0.003 | 7.2 |
| 1280 | 1.000 ± 0.000 | 1280 | 0.607 ± 0.409 | 776.4 | 0.014 ± 0.003 | 17.5 | 0.039 ± 0.029 | 50.3 | 0.006 ± 0.002 | 7.3 |

Five distinct coverage strategies emerge:

**CausalSweep** achieves 100% coverage at every N (deterministic BLOCK of all genes). Despite this, scores degrade from 0.983 to 0.800 — full coverage is necessary but not sufficient when the prediction formula's independence assumption fails at large N.

**Sonnet** achieves 100% gene coverage at N≤80 (std=0) and maintains 61% (776 genes) at N=1280, but with very high variance (std=0.41) — reflecting the bimodal explore-first vs tasks-first strategies described in §5 task-hit analysis. Scores 0.983 at N=1280 despite lower coverage than CausalSweep — reasoning from partial data outperforms formula with full data.

**Qwen 3.5** is the closest LLM to Sonnet — 86–88% coverage at N≤40, declining to 4% (50 genes) at N=1280. It explores 3× more genes than DeepSeek at every N, explaining its higher budget usage.

**DeepSeek V3.1** touches a near-constant ~14–18 genes regardless of N with low variance (std=0.003–0.16). At N=20 this is 69% coverage; at N=1280 it's 1.4%. Yet it scores 0.917 at N=640 with only 16 genes explored — the highest per-gene efficiency of any LLM. The low coverage variance confirms a consistent targeted strategy rather than random gene selection.

**GPT-4o** covers ~6–10 genes at all N (same pattern as DeepSeek in absolute terms) but achieves only baseline-level scores. The difference is not coverage volume but coverage quality — DeepSeek's 16 genes yield far more information than GPT-4o's 7.

**Key insight**: CausalSweep vs Sonnet at N=1280 demonstrates that more data is not better than better reasoning. CausalSweep runs 1471 experiments with 100% coverage and scores 0.800. Sonnet runs ~224 experiments with 61% coverage and scores 0.983.

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
Full exploration does not guarantee success.

Inspecting seed 3's failure reveals why: the missed prediction task used interventions
**DAMPEN G272 + BOOST G799**, and Sonnet predicted `displacement-score` as 0.413 vs
ground truth 0.274 (error 0.14, just over the ±0.10 threshold). The other two phenotypes
were predicted correctly. This is not an information gap — Sonnet had perturbed both G272
and G799 before seeing the task (prospective=1.0, 100% coverage). The failure is a
*reasoning* error: predicting the combined nonlinear effect of a DAMPEN+BOOST double
intervention on a specific phenotype.

This connects directly to the §4 strategy finding: Sonnet uses **97.7% BLOCK** at N=1280.
BLOCK experiments are optimal for network *discovery* (hard do-calculus interventions that
reveal downstream dependencies), but the prediction task required reasoning about DAMPEN
and BOOST effects. With almost no DAMPEN observations in its experimental history, Sonnet
had to extrapolate from BLOCK data — and got the nonlinear interaction wrong by a small
margin. The failure is a consequence of Sonnet's own efficient exploration strategy, not
organism complexity.

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
a near-complete collapse in coverage fraction (95% → 61%). DeepSeek scores 0.917 at N=640
with only 2.5% coverage. Adding genes does not make the prediction tasks harder — it
increases exploration cost, which capable models absorb through different strategies
(Sonnet: broad sweeps; DeepSeek: targeted experiments). The task difficulty is set by the
prediction task structure (which genes, which cross-module interactions), not by N.

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

- **DeepSeek's targeted strategy**: what governs which ~16 genes DeepSeek selects? If it's
  reading the organism description and prioritising genes mentioned in phenotype readouts or
  module hubs, that would explain its high per-experiment efficiency. Log analysis could
  reveal whether its gene selection is random, sequential, or topology-informed.
- **Qwen's decline at large N**: Qwen drops from 0.926 at N=40 to 0.783 at N=1280, more
  steeply than DeepSeek (0.850 → 0.817). Is this because Qwen's broader coverage strategy
  becomes less effective when it can only reach 4% of genes, while DeepSeek's targeted
  approach is N-invariant?
- Budget scaling experiment (fix N, vary budget) would test whether any model is
  strategy-limited or compute-limited at large N.
