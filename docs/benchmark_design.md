# LEMONOIDS Benchmark Design

A reference document for the benchmark's design decisions, parameters, and
invariants. Intended for contributors, reviewers, and anyone extending the
codebase — not a substitute for the paper, but the place to find the *why*
behind design choices.

---

## 1. Purpose and Design Principles

LEMONOIDS is a benchmark for evaluating whether LLM agents can perform
**causal reasoning** over unknown systems — synthetic networks with
biological-style complexity (feedback loops, latent confounders, nonlinear
dynamics) but invented vocabulary — rather than pattern matching against
training data.

**Core principles:**

- **Invented vocabulary**: all gene names, module labels, signal names, and
  phenotype labels are synthetic (e.g. G001, "adaptation-score"). No real
  biology terms appear. This prevents retrieval bias — a model cannot succeed
  by recalling real gene functions.

- **Causal reasoning over correlation**: prediction tasks (see §8) are designed
  to require understanding of network structure, not just statistical associations.
  Shared-readout gene pairs interact non-linearly through the sigmoid; additive
  approximations systematically fail.

- **Closed information environment**: the agent sees only what it chooses to
  measure. The simulated gene regulatory network (GRN) — the wiring diagram of
  which genes regulate which — is unknown to the agent; ground truth is never
  revealed. Success requires reasoning from perturbation evidence — whether by
  building a full internal causal model or by targeted inference about the
  specific genes relevant to each prediction task.

- **Verified difficulty**: every generated organism passes structural and
  functional checks (see §6) before use in experiments. Difficulty is
  determined by topological parameters — feedback density, observability,
  latent gene fraction, sigmoid steepness — not by network size. Two organisms
  with the same N can have very different difficulty; difficulty tiers are
  defined by these structural axes, not as a post-hoc label.

---

## 2. Organism Structure

An organism is a gene regulatory network (GRN) with the following components:

```
Genes (G001–GXXX)
  ├── Observable  — agent can BLOCK / BOOST / DAMPEN and observe expression
  ├── Latent      — hidden confounders; influence the network but invisible
  └── (all genes participate in GRN dynamics)

Modules         — functional groups; intra-module edges are denser
Signals         — external inputs that activate/inhibit target genes
Phenotypes (3)  — observable outputs computed from a weighted sigmoid readout
```

**Gene regulatory dynamics** follow a discrete-time synchronous sigmoid update rule
(gene values are continuous in [0,1]; time steps are discrete):

```
x_i(t+1) = sigmoid(bias_i + Σ_j w_ij · x_j(t) + signal_contrib_i(t)) + ε_i
```

where:
- `sigmoid(z, k) = 1 / (1 + exp(-k·z))`, `k` = steepness (tier-dependent, see §3)
- `w_ij` = regulatory weight from gene j to gene i (positive = activation, negative = inhibition)
- `signal_contrib_i(t)` = sum of active signal strengths for signals targeting gene i
- `ε_i ~ N(0, σ²)` = measurement noise added to the final converged state (σ tier-dependent)

The network iterates until convergence (max |x(t+1) − x(t)| < tolerance, up to 500 steps).
Convergence is not guaranteed for all topologies but is achieved in practice for the
parameter ranges used. **Ground truth for scoring is computed at σ=0** (noiseless); agents
observe the noisy steady state.

**Phenotype readout** (computed independently of dynamics):

```
phenotype_p = sigmoid(bias_p + Σ_i w_pi · x_i)
```

Every observable gene is a primary input to exactly one phenotype (round-robin
partition). Bias is set so the baseline phenotype = 0.5 (see §4, step 13).

---

## 3. Difficulty Tiers

Three tiers tuned to create a gradient from near-linear to highly nonlinear:

| Parameter | Description | Easy | Medium | Hard |
|-----------|-------------|------|--------|------|
| Observability | Fraction of genes the agent can target and observe. Non-observable genes still participate in GRN dynamics but are invisible to the agent. | 0.80 | 0.60 | 0.50 |
| Intra-module edge density | Probability of a regulatory edge between two genes in the same functional module. Higher density = more local interactions. | 0.25 | 0.40 | 0.50 |
| Inter-module edge density | Probability of a regulatory edge between genes in different modules. Controls cross-module coupling; low = near-independent modules. | 0.04 | 0.08 | 0.15 |
| Inhibition fraction | Fraction of edges that are inhibitory (w < 0). Higher inhibition creates more complex, non-monotone response patterns. | 0.20 | 0.30 | 0.40 |
| FFLs (fraction × n_genes) | Feed-forward loops injected into the GRN. A coherent FFL (A→B, A→C, B→C) creates sign-consistent indirect paths that amplify or buffer perturbation effects. | 0.07 (~1) | 0.13 (~3) | 0.20 (~4) |
| Feedback loops (fraction × n_genes) | Mutual-activation feedback loops (A→B, B→A). Absent in easy — feedback creates bistability and history-dependence, making steady-state prediction harder. | 0.0 | 0.13 (~3) | 0.27 (~5) |
| Sigmoid steepness (β) | Controls nonlinearity of the sigmoid. Low β ≈ linear response; high β ≈ switch-like. Drives the difficulty of reasoning about combined intervention effects. | 0.7 | 1.0 | 2.0 |
| Noise σ | Std dev of Gaussian noise added to gene expression at steady state. Agents observe noisy measurements; ground truth for scoring is noiseless. | 0.005 | 0.01 | 0.03 |
| Latent gene fraction | Fraction of genes that are non-observable AND guaranteed to shift ≥1 phenotype by >0.05 — true hidden confounders. Subset of non-observable genes; zero in easy/medium. | 0.0 | 0.0 | 0.25 |

**Aliases**: `easy` = `prokaryote`, `medium` = `simple_eukaryote`,
`hard` = `complex_eukaryote`. `medium` is the default and canonical tier.

At n=20 genes this produces:

| | Easy | Medium | Hard |
|---|---|---|---|
| Observable genes | 16 | 12 | 10 |
| Latent genes (guaranteed confounders) | 0 | 0 | 5 |
| Other non-observable genes | 4 | 8 | 5 |
| GRN edges (typical) | ~26–42 | ~57–75 | ~87–121 |

---

## 4. Generation Pipeline

`generate_organism()` produces a deterministic organism from a `(seed, parameters)`
pair. The 13 steps and their key guarantees:

**Why this order?** Steps 1–7 establish structure before any simulation. Steps 8–9
(observable/latent selection) must precede step 11 (phenotype readouts) — readouts
are built exclusively from observable genes, and latent candidates are drawn from the
non-observable pool, so both pools must be fixed first. Step 10 (baseline simulation)
must precede steps 12–13, which use simulated phenotype values to verify latent
relevance and re-centre biases. Step 13 must follow step 11 because it uses the
finalised readout weights.

| Step | What happens | Why / Key guarantee |
|------|--------------|---------------------|
| 1 | Assign gene IDs (G001–GXXX) | Invented labels; no real gene names |
| 2 | Partition genes into modules (round-robin) | Functional groupings; ≥1 gene per module guaranteed |
| 3 | Sample GRN edges (Erdős–Rényi independently per module pair) | Intra-module density > inter-module density by design; density independent of n so complexity scales with tier parameters, not network size |
| 4 | Inject feed-forward loops: coherent triples A→B, A→C, B→C | FFLs create indirect causal paths that amplify or buffer perturbations non-additively; count = round(ffl_fraction × n_genes) |
| 5 | Inject feedback loops: mutual activation pairs A→B, B→A | Feedback creates history-dependence and potential bistability, making steady-state prediction harder; absent in easy tier |
| 6 | Assign signals with random target gene sets | Each signal activates or inhibits a subset of genes; count and max targets scale with n_genes |
| 7 | Sample per-gene biases from uniform distribution | Sets each gene's baseline activation level independently of the network |
| 8 | Select observable genes (≥1 per module, up to observability × n_genes) | Ensures module coverage; done before dynamics so latent connectivity can be checked against the observable set |
| 9 | Select latent gene candidates from non-observable pool | Latent genes are a subset of non-observable genes earmarked as guaranteed confounders (relevance enforced in step 12) |
| 10 | Compile dynamics rule; simulate to steady state → baseline | Establishes the healthy baseline state all perturbations are measured relative to |
| 11 | Build phenotype readouts (round-robin over observable genes) | Every observable gene assigned to exactly one phenotype readout; weight floor \|w\| ≥ 0.5 prevents nominally-present but silent contributions |
| 12 | Latent gene relevance check | Each latent gene probed by BLOCK simulation; if \|phenotype shift\| ≤ 0.05, gene is added directly to a readout — guarantees every latent gene is a true confounder |
| 13 | Phenotype bias re-centering | Set `bias_p = −Σ(w_pi × baseline_expr_i)` so every phenotype starts at exactly 0.5; prevents saturated baselines where individual knockouts are invisible |

**Why steps 11–13 matter**: without them, organisms can have silent observable
genes (no readout entry), trivially additive tasks (genes from different
readouts are independent), irrelevant latent genes (no phenotype path), and
saturated baselines (sigmoid flat, individual knockouts invisible). All four
were artefacts in earlier generation code and are now guaranteed to be absent.

---

## 5. Disease Mode

Disease organisms are generated by `generate_disease_organism()`, which wraps
`generate_organism()` and applies one or more malfunctions:

| Malfunction type | Effect | Corrective intervention |
|-----------------|--------|------------------------|
| `LOCK_HI` | Gene bias set to +20 (always active) | BLOCK the gene |
| `LOCK_LO` | Gene bias set to −20 (always silent) | BOOST the gene |
| `PERSIST` | Signal chronically overactivated (10× strength) | Deactivate the signal |

**Detectability guarantee**: every disease organism satisfies:
1. ≥1 phenotype falls outside the healthy range (±0.15 of baseline)
2. A single corrective intervention restores ≥1 aberrant phenotype

Note: the detectability threshold (±0.15) is intentionally looser than the prediction
accuracy threshold (±0.10). They serve different purposes: detectability ensures the
disease produces a *visible* phenotypic signal the agent can observe; prediction accuracy
measures the precision of the agent's forward model. A phenotype that is aberrant (e.g.
0.68, shift of 0.18 from baseline 0.50) is well within the agent's observable range even
though predicting it within ±0.10 requires a precise causal model.

Malfunction target genes are never latent (agent must be able to target them
for rescue). `n_diagnosis_alternatives` counts how many other malfunctions
produce a phenotype signature within 0.1 of the true disease — a measure of
diagnosis ambiguity.

---

## 6. Verification

`verify_organisms.py` checks three properties per seed:

1. **Structural**: correct n_genes, n_latent, n_phenotypes per tier preset
2. **Additivity**: prediction tasks not solvable by summing single-gene BLOCK
   effects (max additive prediction error > 0.15 for ≥1 task). This threshold
   is more generous than the scoring threshold (±0.10) — it screens out only
   the most trivially additive organisms; only medium/hard are guaranteed
   non-trivial (see verification results below). See §8 for the full prediction
   task definition.
3. **Latent relevance** (hard only): every latent gene shifts ≥1 phenotype by
   > 0.05 when blocked

Verification results for n=20, seeds 0–19:

| Tier | Pass rate | Notes |
|------|-----------|-------|
| Easy | 17/20 | 3 additive — inherent to near-linear dynamics; reported transparently |
| Medium | 20/20 | |
| Hard | 20/20 | All latent genes relevant, 0 additive tasks |

---

## 7. Scaling

At the canonical n=20 design point the following defaults hold; they scale
automatically for larger networks:

| Parameter | Formula | n=20 | n=40 | n=80 | n=160 |
|-----------|---------|------|------|------|-------|
| `n_modules` | `max(4, round(n/5))` | 4 | 8 | 16 | 32 |
| `n_signals` | `max(3, round(n/7))` | 3 | 6 | 11 | 23 |
| Signal max targets | `max(3, round(n/7))` | 3 | 6 | 11 | 23 |
| `n_phenotypes` | 3 (default) | 3 | 3 | 3 | 3 |
| `n_prediction_tasks` | 2 (default) | 2 | 2 | 2 | 2 |
| Budget | `n_genes + n_signals + 8` | 31 | 54 | 99 | 191 |

The scaling rule keeps ~5 genes/module and ~1/7 signal coverage at any size.
`n_phenotypes` and `n_prediction_tasks` are configurable parameters of
`generate_organism()` — they are held at 3 and 2 respectively across all
paper v1 runs to keep the benchmark interface constant, but can be increased
for future study designs.

**Why `n_prediction_tasks = 2`**: two tasks provide enough signal to evaluate
cross-module interaction reasoning (see §8) while keeping budget consumption modest.
More tasks would require more budget or leave less room for discovery experiments;
fewer would make the prediction score too noisy (binary pass/fail per session).

**Why `budget = n_genes + n_signals + 8`**: the `n_genes + n_signals` term covers one
experiment per targetable element — the minimal systematic sweep. The `+8` provides
headroom for follow-up experiments (e.g. multi-gene probes, re-testing after disease
observation). At n=20 medium this gives budget=31 vs 23 elements, leaving ~8 free
experiments for targeted follow-up.

Vocabulary pools (module labels: 20, signal labels: 15) cycle with a numeric
suffix when exhausted (e.g. `"vortex-2"`), which occurs above n ≈ 100.

---

## 8. Tasks and Scoring

The benchmark defines up to three task types depending on mode:

| Task | Mode | Description |
|------|------|-------------|
| Predict | Both | Predict phenotype values for held-out multi-gene interventions |
| Diagnose | Disease | Identify the malfunctioning gene/signal and malfunction type |
| Rescue | Disease | Test a corrective intervention that restores phenotypes to healthy range |

### Prediction tasks

Each prediction task specifies a multi-gene intervention the agent has not
directly run, and asks the agent to predict the resulting steady-state phenotype
values. Key properties:

- **Held-out**: the exact intervention cannot be run before predicting — the
  agent must infer outcomes from its causal model of the network.
- **Sequential reveal**: tasks are released one at a time. Task 2 is not visible
  until task 1 is submitted, so the agent cannot observe task 2's intervention
  directly before predicting it.
- **Non-trivial shift**: each task produces a ≥0.10 phenotype shift from
  baseline — tasks cannot be answered by predicting the baseline value.
- **Non-additive by design**: each task targets genes within the same phenotype
  readout. Their combined effect is non-linear (sigmoid interaction), so summing
  individual BLOCK/BOOST effects gives the wrong answer. Correct prediction
  requires reasoning about interaction effects.
- **Default n=2** per session (configurable; fixed at 2 for all paper v1 runs).

### Scoring

All scores are in [0, 1], higher is better. Ground truth is computed noiselessly
(`noise=False`) even though agents observe noisy measurements — scoring against a
noisy target would make the benchmark stochastic across re-runs. At hard tier
(σ=0.03), ±0.10 represents a ~3σ tolerance, so measurement noise alone is not
penalised.

| Task | Metric | How scored |
|------|--------|------------|
| Prediction | Accuracy | Fraction of phenotypes within ±0.10 of ground truth, averaged over tasks |
| Diagnosis | Score | 1.0 exact (gene + type) · 0.5 correct gene wrong type · 0.0 wrong |
| Rescue | Fraction | Fraction of aberrant phenotypes restored to healthy range |
| Composite | — | Healthy: pred_acc · Disease: mean(pred_acc, diagnosis, rescue) |

MSE is computed and logged per prediction task but is not used in final scoring.
Scores are only revealed via `get_summary()` at session end.

---

## 9. Agent Interface

The agent interacts with an `ExperimentSession` via 7 tools:

| Tool | What it does |
|------|-------------|
| `get_organism_info()` | Gene names, signals, observable phenotypes, budget, baseline phenotypes |
| `run_experiment(interventions)` | Apply BLOCK/BOOST/DAMPEN to any genes; returns steady-state expressions + phenotypes |
| `submit_prediction(task_id, values)` | Submit phenotype predictions for a prediction task |
| `get_prediction_tasks()` | List prediction tasks (gene interventions to predict) |
| `submit_malfunction_hypothesis(target, type)` | Commit to a diagnosis (disease mode); locked on first call |
| `test_rescue(intervention)` | Test a corrective intervention against the disease state |
| `get_summary()` | Retrieve all scores (only meaningful at session end) |

**Intervention types**: `BLOCK` (expression → 0), `BOOST` (expression → 1),
`DAMPEN` (clamps expression to ≤ 0.15 — a partial suppression, distinct from full BLOCK).

**Budget**: `n_genes + n_signals + 8` experiments total (see §7 for rationale).
Each `run_experiment` or `test_rescue` call costs 1 unit. `get_organism_info()`
and `get_prediction_tasks()` are free (do not consume budget).

**LLM parameters**: all models run with `max_tokens=16384`, `temperature=1.0` (default).
Tool calling uses the provider's native function-calling API. Each session is a fresh
context — no memory carried across seeds.

**System prompt**: agents are told the organism name, that genes regulate each other and
produce phenotypes, that they have a budget of experiments, and that their goal is to
characterise the network well enough to predict novel intervention outcomes. The system
prompt does not reveal network topology, gene functions, or any biology-domain knowledge.
Full prompt text is in `lemonoids/agent.py`.

---

## 10. Baselines

Two non-LLM baselines establish performance bounds.

**Heuristic baseline**: systematically BLOCKs each gene one at a time and predicts
intervention outcomes using an additive model (sum of individual BLOCK effects). For
disease mode, exhaustively enumerates all gene × malfunction-type combinations and
selects the one whose predicted phenotype signature best matches the observed disease
state. Uses the same tool interface as LLM agents.

**Random baseline**: predicts 0.5 for all phenotypes (the baseline value), runs no
experiments, and submits a randomly chosen gene and malfunction type as its hypothesis.
Scores zero on all strategy and effort metrics. Provides a lower bound: any model that
cannot beat random has learned nothing from perturbation data.

Notable behaviours documented in `docs/part1_results.md`:
- Heuristic scores below random on hard healthy — additive prediction fails on
  high-feedback organisms where the nonlinear sigmoid dominates.
- Random scores ~0.667 on all tiers at ±0.10 (structural floor: ~2/3 phenotypes
  fall near the 0.5 baseline, which random predicts exactly).

---

## 11. Reproducibility

**Generation freeze**: all paper v1 results use generation code frozen at tag
`v1-generation-freeze-2` (commit `57f7be7`). Results from the initial freeze
(`v1-generation-freeze`) were invalidated by organism quality fixes in PR #21.

**Seed selection**: seeds 0–19 per sweep, pre-screened by `select_seeds.py` to
ensure all disease organisms are valid (rescuable, ≥1 aberrant phenotype). Seed 14
is excluded from all disease sweeps — the organism is too stable for any malfunction
to produce aberrant phenotypes.

**Determinism**: generation is fully deterministic given `(seed, parameters)`.
All gene orderings use `sorted()` (not `list(set())`) to avoid Python hash-seed
non-determinism across processes (fixed in PR #28).

**Results**: raw session logs are stored locally (gitignored). Canonical results
tables are in `docs/part1_results.md` (Part 1) and `docs/part2_results.md` (scaling).

---

## 12. Limitations and Extensions

Known limitations of the current design, and planned or proposed extensions.
Organised by the reviewer concern each addresses.

### Network realism

The synthetic GRNs use invented vocabulary and randomly sampled topology, but
their structural parameters (FFL frequency, feedback density, degree distributions)
have not been systematically compared to real biological GRN databases
(e.g. RegulonDB, BioGRID). The claim of "biological-style complexity" rests on
the use of established GRN dynamics models (Mjolsness et al. 1991; Karlebach &
Shamir 2008) and qualitatively plausible parameter ranges, not on a quantitative
topology match.

**Planned**: a topology validation study comparing generated network statistics to
real GRN databases at equivalent network sizes. This would strengthen the
biological plausibility claim without changing the benchmark itself.

### Reasoning patterns vs. retrieval

Invented vocabulary removes factual retrieval bias, but does not eliminate the
possibility that models have encountered structurally similar causal reasoning
problems in training (e.g. synthetic causal graphs, textbook perturbation
exercises). A model could be pattern-matching a known reasoning strategy rather
than performing novel inference.

**Planned**: *backwards organisms* — organisms where the expected direction of
regulatory effects is systematically inverted relative to typical GRN conventions.
A model relying on learned reasoning heuristics would perform worse on backwards
organisms; a model reasoning from perturbation evidence would not. See IDEAS.md
for design notes.

### Prompt sensitivity

All models are evaluated with the same system prompt (see §9). Model rankings
could shift under different prompt phrasings, levels of task specification, or
chain-of-thought encouragement. Prompt sensitivity is a known confound for LLM
benchmarks and has not been ablated here.

**Acknowledged limitation**: the benchmark tests agent performance under a fixed,
reasonable prompt, not best-possible performance for each model. A prompt
sensitivity ablation (varying phrasing and instruction detail across a small seed
set) would bound this confound.

### Statistical power

20 seeds per model × sweep gives limited statistical power, particularly at hard
tier where scores are low and variance is high. No confidence intervals are
reported in the current results tables.

**Planned**: bootstrap confidence intervals on all aggregate metrics. No re-runs
required — intervals can be computed from existing session logs.

### No human baseline

Without a human baseline, it is unclear whether the hard tier is hard for humans
or only for current LLMs. A human baseline on a small seed set (5–10 organisms)
would calibrate difficulty and make the benchmark's discriminative range
interpretable.

**Planned**: single-session human evaluation on hard tier seeds, using the same
tool interface as LLM agents.

### Synchronous discrete-time dynamics

The GRN uses synchronous discrete-time updates, which differ from real biological
GRNs (continuous, asynchronous, stochastic at the molecular level). This is a
deliberate modelling choice for tractability and reproducibility: the benchmark
tests an agent's ability to reason about a well-defined formal system, not to
simulate real biology. Agents are given the update rule; there is no hidden
biological realism the model needs to recover.

**Extension**: asynchronous update variants would test robustness of agent
strategies to dynamics model mismatch.

### Easy tier as discriminator

The easy tier produces near-linear organisms where the random baseline scores
~0.80 composite. This makes easy a weak discriminator between models. It is
useful as a sanity check (any model should score above random) and as a floor
for interpretation, but paper results and comparisons focus on medium and hard.
3/20 easy organisms have near-additive prediction tasks — an inherent property
of low-feedback networks, reported transparently (see §6).

### Prior knowledge integration

The current benchmark makes all prior knowledge uninformative by design. A
natural extension is to test whether agents can integrate synthetic prior
knowledge (organism-family datasheets in invented vocabulary) with perturbation
evidence, and whether knowledge helps most where pure causal reasoning fails —
i.e. at high complexity. See `docs/part3_knowledge_extension.md` for a full
design proposal.
