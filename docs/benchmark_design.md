# LUCA Benchmark Design

A reference document for the benchmark's design decisions, parameters, and
invariants. Intended for contributors and anyone extending the codebase —
not a substitute for the paper, but the place to find the *why* behind
design choices.

---

## 1. Purpose and Design Principles

LUCA is a benchmark for evaluating whether LLM agents can perform
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
saturated baselines (sigmoid flat, individual knockouts invisible). Three of
those four are guaranteed absent.

The fourth is not. Drawing a task's genes from the same readout removes the
*independent* case, where the two genes never meet. It does not make the task
non-additive: the two effects still pass through the sigmoid in a range where
adding them happens to land within the ±0.10 scoring threshold. Measured over
seeds 0–19, every easy and every medium task is additively solvable, and 18 of
40 hard tasks are. See §6 and [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) issue 2.

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
2. **Additivity**: whether a prediction task is solvable by measuring each of
   its genes separately, under the intervention type the task asks for, and
   adding the deltas. A task counts as additively solvable when that prediction
   is within the scoring threshold (±0.10) on every phenotype. See §8 for the
   full prediction task definition.

   > **Corrected 2026-11-19.** This check was broken in two ways. It looked up
   > gene ids in a dictionary keyed by gene names, so every measured effect
   > fell back to zero, and it inverted the sign of the effects it did measure
   > while measuring only `BLOCK`. It therefore reported every task at every
   > tier as non-additive. The rates below are the repaired measurement. See
   > [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) issue 3.
3. **Latent relevance** (hard only): every latent gene shifts ≥1 phenotype by
   > 0.05 when blocked

Verification results for n=20, seeds 0–19:

| Tier | Additively solvable tasks | Notes |
|------|---------------------------|-------|
| Easy | **40 of 40** | every task is solvable by adding single-gene effects |
| Medium | **40 of 40** | the default tier does not test non-additivity |
| Hard | **18 of 40** | 22 tasks resist the additive strategy against the stored ground truth; all latent genes relevant |

**The hard figure overstates the design's contribution.** `task.ground_truth`
carries readout noise of `rng.normal(0, noise_sigma * 2)`
(`luca/dynamics.py:120`). At the hard tier that noise has mean 0.072 and
maximum 0.164 against a +-0.10 threshold. Against a noise-free ground truth the
hard tier is **34 of 40**, so only about 6 of the 22 "resisting" tasks resist
because of the sigmoid interaction the design intends. Easy and medium are
40 of 40 under either measure. See `KNOWN_ISSUES.md`, issues 2 and 3.

Reproduce the first column with `pytest tests/test_verify_organisms.py`. It
measures the medium and hard rates twice — once through `verify_organisms.py`
and once through a second path inside the test file. That second path is **not**
independent: it copies `_readout_noise_free_phenotypes` and its
`default_rng(0)` stream, so an error common to both is invisible to it, and the
readout noise above is exactly such an error. The easy rate is measured once,
and the 34 of 40 figure is not pinned by a test at all.

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
  agent must infer outcomes from its causal model of the network. This is
  enforced from 2026-11-19: revealing a task seals its exact gene-and-type
  combination, and `run_experiment` and `test_rescue` refuse it at no budget
  cost until the task is answered. Before that date the claim was stated but
  not enforced; see [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) issue 1.
  The seal compares gene-and-type pairs, so it holds only because an
  intervention type the simulator cannot read is itself refused (issue 12).
  Adding a third gene with an unreadable type used to change the combination
  and do nothing, which returned the held-out answer. A signal change is part
  of the comparison: the task's genes under a changed signal is a different
  experiment, and it is allowed.
  The seal was **not** airtight between 2026-11-19 and 2026-11-21. A session
  whose two tasks asked the same question let an agent answer the first,
  unseal the combination, then run it and submit the measured values for the
  second. On medium seed 10 that scored accuracy 1.0; see
  [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) issue 15. A separate escape through a
  signal change is open and bucketed v2; see issue 21, and read a prediction
  score as an upper bound.
- **Distinct within a session**: no two tasks of one organism carry the same
  gene-and-type combination. Enforced from 2026-11-21. The generator rejects a
  candidate whose signature repeats a task already built, using the same
  comparison the seal uses, and raises rather than emitting a duplicate. Before
  that date 7 of 900 organisms over seeds 0–299 asked one question twice.
- **Sequential reveal**: tasks are released one at a time. Task 2 is not visible
  until task 1 is submitted, so the agent cannot observe task 2's intervention
  directly before predicting it.
- **Non-trivial shift**: each task produces a ≥0.10 phenotype shift from
  baseline — tasks cannot be answered by predicting the baseline value.
- **Non-additive by intent, and only at hard in practice**: each task targets
  genes within the same phenotype readout, so their combined effect passes
  through the sigmoid together. The intent is that summing the individual
  effects gives the wrong answer. Measured over seeds 0–19 that holds for 22 of
  40 hard tasks against the stored ground truth, and for none at easy or
  medium, where every task is additively solvable. Against a noise-free ground
  truth the hard count is 6 of 40, not 22: the rest of the gap is readout noise
  in `task.ground_truth`, not the sigmoid. So the intent is met for about one
  task in seven at the hardest tier, and nowhere else. The guarantee is a
  property of the generator, so it is addressed in LUCA v2 rather than patched;
  see [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) issue 2.
- **Default n=2** per session (configurable; fixed at 2 for all paper v1 runs).

### Scoring

All scores are in [0, 1], higher is better. Ground truth is computed noiselessly
(`noise=False`) even though agents observe noisy measurements — scoring against a
noisy target would make the benchmark stochastic across re-runs. At hard tier
(σ=0.03), ±0.10 represents a ~3σ tolerance, so measurement noise alone is not
penalised.

| Task | Metric | How scored | Attempts counted |
|------|--------|------------|------------------|
| Prediction | Accuracy | Fraction of phenotypes within ±0.10 of ground truth, averaged over tasks | **One per task**, a resubmission is refused — but ground truth is disclosed on submission |
| Diagnosis | Score | 1.0 exact (gene + type) · 0.5 correct gene wrong type · 0.0 wrong | **One**, locked on the first call, no feedback |
| Rescue | Fraction | Fraction of aberrant phenotypes restored to healthy range | **The best of every attempt**, full feedback each time |
| Composite | — | Healthy: pred_acc · Disease: mean(pred_acc, diagnosis, rescue) | — |

MSE is computed and logged per prediction task but is not used in final scoring.

**Not every score is withheld to the end.** `submit_prediction` returns the
accuracy, the MSE and the per-phenotype ground truth for that task on the call
itself. The scores that *are* withheld until `get_summary()` are the
**diagnosis** score and the **network reconstruction** score: both
`submit_malfunction_hypothesis` and `submit_network` return only a note. An
earlier version of this line said all scores were withheld; the code
contradicts it.

#### A known asymmetry: one attempt against the best of many

**The three sub-scores are not earned under the same rules, and the composite
averages them as though they were.** This is recorded as issue 9 in
[KNOWN_ISSUES.md](../KNOWN_ISSUES.md). It is disclosed here rather than
changed, because changing it would invalidate every comparison already made.

The three composite sub-scores are earned under three different regimes:

- **Diagnosis is a sealed one-shot.** `submit_malfunction_hypothesis` locks on
  its first call and returns only `{"stored", "note"}` — no score, no hint. The
  agent commits with no feedback at all, and learns the result at
  `get_summary()`.
- **Prediction is one-shot per task, but not sealed.** `submit_prediction`
  scores one answer per task and refuses a second (issue 4), yet it returns the
  accuracy, the MSE and each phenotype's ground truth on that call. A session
  carries two tasks by default (`n_prediction_tasks=2`), so an agent sees
  `task_00`'s exact ground truth and its own accuracy **before** it commits
  `task_01`, and can recalibrate.
- **Rescue is best-of-N.** Every *accepted* `test_rescue` call is scored and
  kept — a refused one returns before the result is stored, which is what
  issues 14 and 24 were about. Each accepted call returns the restored
  fraction, which phenotypes are now in range, and a **count** of previously
  healthy phenotypes the intervention broke, so an agent can hill-climb within
  a session. `evaluate.py` then takes the maximum over the
  attempts; `get_summary()` itself stores the raw list under `rescue_results`
  and computes no maximum.
- **The budget allows many attempts.** `recommended_budget` is
  `n_genes + n_signals + 8`, which is **31** for every canonical disease
  organism at all three tiers. `test_rescue` costs 1 unit, so an agent that
  spends nothing on experiments could make up to 31 scored attempts and keep
  the best.

Two consequences for anyone reading a result:

1. **A diagnosis score and a rescue fraction are not comparable.** A model that
   scores higher on rescue than on diagnosis may simply have had more attempts
   and more feedback, not better understanding. Diagnosis is the only sub-score
   earned blind.
2. **The composite weights a one-shot score equally with a best-of-N score.**
   Report the sub-scores, as `README.md` already recommends, and treat the
   composite as a convenience summary rather than a measurement.

Whether to change the rule — scoring only the first rescue, or scoring the
last, or charging for retries — is deferred to LUCA v2, because every option
moves every existing disease number.

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
Full prompt text is in `luca/agent.py`.

---

## 10. Baselines

Three non-LLM baselines establish performance bounds.

**Heuristic baseline**: systematically BLOCKs each gene one at a time and predicts
intervention outcomes using an additive model (sum of individual BLOCK effects). For
disease mode, it picks the gene whose measured effect on the aberrant phenotypes is
largest and submits `LOCK_HI`; it does not enumerate. Uses the same tool interface as
LLM agents.

**CausalSweep baseline**: the stronger non-LLM bound. It sweeps interventions and, in
disease mode, enumerates gene × malfunction-type combinations, selecting the one whose
predicted phenotype signature best matches the observed disease state. The enumeration
described here used to be attributed to the heuristic baseline, which never did it.

**Random baseline**: predicts 0.5 for all phenotypes (the baseline value), runs no
experiments, and submits a randomly chosen gene and malfunction type as its hypothesis.
Scores zero on all strategy and effort metrics. Provides a lower bound: any model that
cannot beat random has learned nothing from perturbation data.

Notable behaviours, measured over seeds 0-9 at ±0.10 on 2026-11-20:

| tier | heuristic | random |
|---|---|---|
| easy | 0.9333 | 0.6667 |
| medium | 0.8167 | 0.6500 |
| hard | 0.6667 | 0.4667 |

CausalSweep is not in this table. It reports through a different interface and
has not been measured here; do not assume a number for it.

- The heuristic used to score **below** random on medium and hard. That was
  issue 6, an inverted sign in its own arithmetic, not a property of the
  organisms. An earlier version of this file blamed "high-feedback organisms
  where the nonlinear sigmoid dominates". That explanation was wrong and is
  removed.
- Random does not score ~0.667 on all tiers. It scores 0.6667 on easy, 0.6500
  on medium and 0.4667 on hard. The structural floor is real — many phenotypes
  sit near the 0.5 baseline, which random predicts exactly — but it weakens as
  the tier gets harder.

---

## 11. Reproducibility

**Generation freeze**: all paper v1 results use generation code frozen at tag
`v1-generation-freeze-2` (commit `8880d24`). Results from the initial freeze
(`v1-generation-freeze`) were invalidated by organism quality fixes in PR #21.

**Seed selection**: seeds 0–19 per sweep, pre-screened by `select_seeds.py` to
ensure all disease organisms are valid (rescuable, ≥1 aberrant phenotype). Seed 14
is excluded from all disease sweeps — the organism is too stable for any malfunction
to produce aberrant phenotypes.

**Determinism**: generation is fully deterministic given `(seed, parameters)`.
All gene orderings use `sorted()` (not `list(set())`) to avoid Python hash-seed
non-determinism across processes (fixed in PR #28).

**Results**: raw session logs are stored locally (gitignored). Canonical results
tables are in the paper.

---

## 12. Limitations and Extensions

Known limitations of the current design, and planned or proposed extensions.

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
organisms; a model reasoning from perturbation evidence would not. See the paper for results.

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
Every easy prediction task over seeds 0–19 is additively solvable, so the tier
does not test non-additive causal reasoning at all. The earlier figure of 3/20
came from the broken verifier described in §6.

### Prior knowledge integration

The current benchmark makes all prior knowledge uninformative by design. A
natural extension is to test whether agents can integrate synthetic prior
knowledge (organism-family datasheets in invented vocabulary) with perturbation
evidence, and whether knowledge helps most where pure causal reasoning fails —
i.e. at high complexity. See `docs/designs/part3_knowledge_extension.md` for a full
design proposal.
