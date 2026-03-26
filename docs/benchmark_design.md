# LEMONOIDS Benchmark Design

A reference document for the benchmark's design decisions, parameters, and
invariants. Intended for contributors, reviewers, and anyone extending the
codebase — not a substitute for the paper, but the place to find the *why*
behind design choices.

---

## 1. Purpose and Design Principles

LEMONOIDS is a benchmark for evaluating whether LLM agents can perform
**causal reasoning** over unknown biological systems, rather than pattern
matching against training data.

**Core principles:**

- **Invented vocabulary**: all gene names, module labels, signal names, and
  phenotype labels are synthetic (e.g. G001, "adaptation-score"). No real
  biology terms appear. This prevents retrieval bias — a model cannot succeed
  by recalling real gene functions.

- **Causal reasoning over correlation**: prediction tasks are designed to
  require understanding of network structure, not just statistical associations.
  Shared-readout gene pairs interact non-linearly through the sigmoid; additive
  approximations systematically fail.

- **Closed information environment**: the agent sees only what it chooses to
  measure. The GRN is unknown; ground truth is never revealed. Success requires
  building an internal causal model from perturbation evidence.

- **Verified difficulty**: every generated organism passes structural and
  functional checks (see §4) before use in experiments. Difficulty is a
  property of the organism's topology, not a post-hoc label.

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

**Gene regulatory dynamics** follow a continuous sigmoid update rule:

```
x_i(t+1) = sigmoid(bias_i + Σ_j w_ij · x_j(t) + signal_contrib_i(t))
```

where `sigmoid(z, k) = 1 / (1 + exp(-k·z))` and `k` is the steepness
parameter. The network is iterated to steady state before each measurement.

**Phenotype readout** (computed independently of dynamics):

```
phenotype_p = sigmoid(bias_p + Σ_i w_pi · x_i)
```

Every observable gene is a primary input to exactly one phenotype (round-robin
partition). Bias is set so the baseline phenotype = 0.5 (see §4, fix 5).

---

## 3. Difficulty Tiers

Three tiers tuned to create a gradient from near-linear to highly nonlinear:

| Parameter | Easy | Medium | Hard |
|-----------|------|--------|------|
| Observability | 0.80 | 0.60 | 0.50 |
| Intra-module edge density | 0.25 | 0.40 | 0.50 |
| Inter-module edge density | 0.04 | 0.08 | 0.15 |
| Inhibition fraction | 0.20 | 0.30 | 0.40 |
| FFLs (fraction × n_genes) | 0.07 (~1) | 0.13 (~3) | 0.20 (~4) |
| Feedback loops (fraction × n_genes) | 0.0 | 0.13 (~3) | 0.27 (~5) |
| Sigmoid steepness | 0.7 | 1.0 | 2.0 |
| Noise σ | 0.005 | 0.01 | 0.03 |
| Latent gene fraction | 0.0 | 0.0 | 0.25 |

**Aliases**: `easy` = `prokaryote`, `medium` = `simple_eukaryote`,
`hard` = `complex_eukaryote`. `medium` is the default and canonical tier.

At n=20 genes this produces:

| | Easy | Medium | Hard |
|---|---|---|---|
| Observable genes | 16 | 12 | 10 |
| Latent genes | 0 | 0 | 5 |
| GRN edges (typical) | ~26–42 | ~57–75 | ~87–121 |

---

## 4. Generation Pipeline

`generate_organism()` produces a deterministic organism from a `(seed, parameters)`
pair. The 13 steps and their key guarantees:

| Step | What happens | Key guarantee |
|------|--------------|---------------|
| 1 | Gene names G001–GXXX | |
| 2 | Module partition (round-robin) | At least 1 gene per module |
| 3 | GRN edges (Erdős–Rényi per module pair) | Density independent of n |
| 4 | Inject FFLs (coherent A→B, A→C, B→C) | Count scales with n_genes |
| 5 | Inject feedback loops (mutual activation) | Count scales with n_genes |
| 6 | Assign signals | Count and target coverage scale with n_genes |
| 7 | Sample per-gene biases | |
| 8 | Select observable genes | ≥1 per module; fraction = observability |
| 9 | Select latent gene candidates | From non-observable pool |
| 10 | Build dynamics rule; simulate baseline | |
| 11 | Build phenotype readouts (round-robin) | Every observable gene in exactly one readout; weight floor \|w\| ≥ 0.5 |
| 12 | Latent gene relevance check | Each latent gene probed by BLOCK simulation; if \|shift\| ≤ 0.05 added directly to a readout |
| 13 | Phenotype bias re-centering | `bias = −Σ(w_i × baseline_expr_i)` → every phenotype baseline = 0.5 |

**Why steps 11–13 matter**: without them, organisms can have silent observable
genes (no readout entry), trivially additive tasks (genes from different
readouts are independent), irrelevant latent genes (no phenotype path), and
saturated baselines (sigmoid flat, individual knockouts invisible). All four
were artefacts in earlier generation code and are now guaranteed to be absent.

---

## 5. Scaling

At the canonical n=20 design point the following defaults hold; they scale
automatically for larger networks:

| Parameter | Formula | n=20 | n=40 | n=80 | n=160 |
|-----------|---------|------|------|------|-------|
| `n_modules` | `max(4, round(n/5))` | 4 | 8 | 16 | 32 |
| `n_signals` | `max(3, round(n/7))` | 3 | 6 | 11 | 23 |
| Signal max targets | `max(3, round(n/7))` | 3 | 6 | 11 | 23 |
| `n_phenotypes` | fixed | 3 | 3 | 3 | 3 |
| `n_prediction_tasks` | fixed | 2 | 2 | 2 | 2 |
| Budget | `n_genes + n_signals + 8` | 31 | 54 | 99 | 191 |

The scaling rule keeps ~5 genes/module and ~1/7 signal coverage at any size.
`n_phenotypes` and `n_prediction_tasks` are fixed by design — the benchmark
interface is constant regardless of network size.

Vocabulary pools (module labels: 20, signal labels: 15) cycle with a numeric
suffix when exhausted (e.g. `"vortex-2"`), which occurs above n ≈ 100.

---

## 6. Agent Interface

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
`DAMPEN` (expression × 0.5).

**Budget**: `n_genes + n_signals + 8` experiments total. Each `run_experiment`
or `test_rescue` call costs 1 unit. Budget is shared across all tool calls in
the session.

**Modes**:
- *Healthy*: tasks are `predict` only (2 prediction challenges)
- *Disease*: tasks are `predict` + `diagnose` + `rescue`

---

## 7. Scoring

All scores are in [0, 1], higher is better.

**Prediction accuracy** (per task):
```
accuracy = (number of phenotypes within ±0.10 of ground truth) / n_phenotypes
```
MSE is also computed and logged per task but is not used in scoring.

**Diagnosis score** (disease mode):
```
1.0  correct target AND correct malfunction type (exact match)
0.5  correct target, wrong malfunction type (partial credit)
0.0  wrong target
```

**Rescue score** (disease mode):
```
fraction of aberrant phenotypes restored to healthy range by the proposed intervention
```

**Composite score**: unweighted mean of all active task components.
- Healthy: composite = prediction accuracy
- Disease: composite = mean(prediction accuracy, diagnosis, rescue)

Ground truth is computed noislessly (noise=False) from the true organism
dynamics. Scores are only revealed via `get_summary()` at session end.

---

## 8. Disease Mode

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

Malfunction target genes are never latent (agent must be able to target them
for rescue). `n_diagnosis_alternatives` counts how many other malfunctions
produce a phenotype signature within 0.1 of the true disease — a measure of
diagnosis ambiguity.

---

## 9. Verification

`experiments/paper_v1/verify_organisms.py` checks three properties per seed:

1. **Structural**: correct n_genes, n_latent, n_phenotypes per tier preset
2. **Additivity**: prediction tasks not solvable by summing single-gene BLOCK
   effects (max error > 0.15 threshold for ≥1 task)
3. **Latent relevance** (hard only): every latent gene shifts ≥1 phenotype by
   > 0.05 when blocked

Verification results for n=20, seeds 0–19 (post PR #21):

| Tier | Pass rate | Notes |
|------|-----------|-------|
| Easy | 17/20 | 3 additive — inherent to near-linear dynamics |
| Medium | 20/20 | |
| Hard | 20/20 | All latent genes relevant, 0 additive tasks |
