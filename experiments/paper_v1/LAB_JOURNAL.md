# Paper v1 — Lab Journal

A running record of experiments, fixes, observations, and decisions.
Not a polished results doc — write freely, entries in reverse chronological order within each section.

---

Last updated: 2026-03-18. **Full benchmark run complete — 560/560 seeds clean (N=20 all, 7 models × 4 sweeps).** See §10 for final results table.

> **Note (2026-03-16):** All results in §1–6 were produced with the old generation code and are
> **invalidated** by PR #21. The canonical benchmark re-run uses the plan in §9.

---

## Composite Score (mean ± std)

| Model | Easy (healthy) | Medium (healthy) | Hard (healthy) | Medium (disease) | N ok (E/M/H/D) |
|---|---|---|---|---|---|
| heuristic | 0.717±0.159 | 0.725±0.132 | 0.717±0.176 | 0.553±0.193 | 20/20/20/19 |
| claude-sonnet-4-6 | 1.000±0.000 | 0.983±0.050 | 0.867±0.125 | 0.866±0.166 | 20/20/20/19 |
| claude-opus-4-6 | 1.000±0.000 | 0.983±0.050 | 0.908±0.111 | 0.907±0.134 | 20/20/20/18 |
| gpt-4o | 0.975±0.060 | 0.843±0.090 | 0.833±0.132 | 0.478±0.138 | 20/17/19/18 |
| gpt-4.1 | 0.941±0.098 | 0.833±0.136 | 0.756±0.159 | 0.567±0.215 | 17/18/15/**10** |
| gpt-5.1 | 0.975±0.079 | 0.895±0.135 | 0.794±0.157 | 0.597±0.163 † | 20/19/17/**6** |

> Seed 14 excluded from disease sweeps across all models — organism is too stable, no malfunction
> produces aberrant phenotypes after 10 generation attempts (consistent `RuntimeError`).

---

## Disease Mode Breakdown (medium, valid seeds only)

| Model | Pred acc | Diagnosis | Rescue | Composite | N valid |
|---|---|---|---|---|---|
| heuristic | 0.711 | 0.158 | 0.789 | 0.553 | 19 |
| claude-sonnet-4-6 | 0.965 | 0.632 | 1.000 | 0.866 | 19 |
| claude-opus-4-6 | 0.944 | 0.778 | 1.000 | 0.907 | 18 |
| gpt-4o | 0.803 | 0.056 | 0.759 | 0.478 | 18 |
| gpt-4.1 | 0.900 | 0.200 | 0.815 | 0.567 | 10 |
| gpt-5.1 | 1.000 | 0.250 | 0.833 | 0.694 | 4 |

---

## Key Findings

### 1. Claude dominates on hard and disease; all models ceiling on easy
Claude (both Sonnet and Opus) score 1.000 on easy — as does GPT (0.94–0.98). Easy tier
is near-saturated and provides little discrimination. Hard and disease mode are the
informative regimes. Opus edges Sonnet on hard (0.908 vs 0.867) and disease (0.907 vs 0.866).

### 2. Diagnosis is the hardest sub-task
Rescue fraction is surprisingly high even for GPT models (0.76–0.83), suggesting models can
find working interventions by trial-and-error without correctly identifying the malfunction.
Diagnosis score is where the gap opens sharply: Claude Opus 0.778, Sonnet 0.632, gpt-5.1 0.250,
gpt-4o 0.056. GPT models largely fail to commit to the correct malfunction hypothesis.

### 3. Heuristic stays flat across difficulty tiers
Heuristic composite is ~0.72 on easy/medium/hard healthy — almost no degradation with
complexity. This is expected: systematic BLOCK sweep + additive prediction doesn't model
feedback, so it neither improves nor degrades relative to difficulty. It provides a
meaningful lower bound but is not a strong baseline above easy tier.

### 4. GPT disease failures are a context exhaustion problem, not a scoring problem
GPT models (especially gpt-5.1 and gpt-4.1) have many `None` results in disease mode:
- gpt-5.1: only 4/20 valid seeds (16 context failures)
- gpt-4.1: 10/20 valid seeds
- gpt-4o: 18/20 valid seeds (most robust)

Root cause: disease mode has a larger tool schema + longer system prompt + 3 active tasks,
and GPT models batch 5–10 tool calls per turn (vs Claude's 2–3), generating large tool-result
messages that exhaust the context window. Same seeds fail across GPT model versions because
organism topology (not model randomness) determines response verbosity.

The gpt-5.1 disease composite of 0.694 is computed on only 4 seeds — likely the easiest
organisms — and is not representative. Report cautiously or exclude from primary comparison.

**For the paper:** report GPT disease results with the valid-N caveat prominently. The
failure mode itself is a finding worth discussing — it reveals a practical limitation of
aggressive tool-call batching under long-context conditions.

### 5. Difficulty scaling discriminates model families
Easy → Hard drop:
- Claude Sonnet: 1.000 → 0.867 (−0.133)
- Claude Opus:   1.000 → 0.908 (−0.092)
- gpt-5.1:       0.975 → 0.794 (−0.181)
- gpt-4o:        0.975 → 0.833 (−0.142)
- gpt-4.1:       0.941 → 0.756 (−0.185)
- heuristic:     0.717 → 0.717 (0.000 — flat by design)

The gap between Claude and GPT widens with difficulty, consistent with the hypothesis
that hard organisms require genuine causal modelling rather than pattern matching.

> † gpt-5.1 disease: only 6/20 valid seeds after all re-run attempts — see §6.

---

## 6. gpt-5.1 Disease: Re-run Attempts and Decision

### What we tried
Three re-runs after fixing the `finish_reason=length` recovery message:
1. **No cap** (original): 4/20 valid. Context window exhausted silently.
2. **max_completion_tokens=4096**: 5/20 valid. Too aggressive — model cut off mid-reasoning,
   diagnosis=0.000 on all, budget used only 29%. Cap truncates output per turn but doesn't
   help with accumulated input context.
3. **max_completion_tokens=16384**: 6/20 valid. Marginal improvement. Same root cause.

### Root cause
`max_completion_tokens` caps *output* per turn; it does not limit the *input* context that
accumulates as tool results pile up. gpt-5.1 batches 5–10 tool calls per turn, each
returning a full steady-state result. By mid-session the message history is 50k+ tokens.
No per-turn output cap prevents this.

### Decision: stop re-running, treat as a finding
Further re-runs are unlikely to help without architectural changes (e.g. history
summarisation, truncating tool results). The failure mode is real and reproducible.

**For the paper — two options:**
- **Option A**: Report gpt-5.1 disease as 6/20, composite 0.597±0.163, with a prominent
  caveat that N is too small for reliable comparison. Include in table with a dagger (†).
- **Option B**: Exclude gpt-5.1 from the disease results table entirely; move it to a
  failure-modes subsection as a case study of context exhaustion.

Leaning toward **Option B**: the 6 valid seeds are likely the easiest organisms (selection
bias), making the 0.597 score unrepresentative. The story is more honest as a failure mode
than as a noisy data point.

---

## 7. Organism Generation Quality (PR #21, 2026-03-16)

Four artefacts identified and fixed in `lemonoids/generation.py` and `lemonoids/experiment.py`.

### Pipeline overview (post-fix)

| Step | What happens |
|------|--------------|
| 1–7  | Gene names, module partition, GRN edges (Erdős–Rényi + FFLs + feedback), signals, gene biases |
| 8    | Observable gene selection — at least one per module, `ceil(observability × 20)` total |
| 9    | Latent gene candidates — drawn from non-observable pool (hard only: 5/20 genes) |
| 10   | Dynamics rule compiled; GRN simulated to steady state → `baseline_state` |
| 11   | Phenotype readouts built from observable genes only, round-robin across 3 phenotypes |
| 12   | Latent gene relevance check — each probed by BLOCK simulation; irrelevant genes added directly to a readout |
| 13   | Phenotype bias re-centering — `bias = −Σ(w_i × baseline_expr_i)` so every phenotype starts at 0.5 |

### Fixes and root causes

**Fix 1 — Observable-first readout construction**
Root cause: readouts were sampled from all 20 genes before observable genes were selected.
~60% of observable genes were absent from any readout → zero phenotype effect when blocked.
Fix: select observable genes in step 8, build readouts from them only in step 11.

**Fix 2 — Round-robin coverage guarantee**
Root cause: random readout sampling left some observable genes without any readout entry.
Fix: `obs[i] → phenotype[i % 3]` — every observable gene in exactly one readout. Weight
floor |w| ≥ 0.5 prevents nominally-present but silent connections.

**Fix 3 — Shared-readout task pairs** (`experiment.py`)
Root cause: random cross-module gene pairs were often from different readouts → tasks trivially
additive (sum of independent single-gene effects predicted the combined outcome within ±0.15).
Fix: `_generate_tasks` now prefers two genes from the same phenotype readout; sigmoid nonlinearity
between co-readout genes makes the combined effect non-additive.

**Fix 4 — Latent gene relevance guarantee**
Root cause: latent genes had no guaranteed path to phenotypes. A GRN edge to an observable gene
isn't sufficient — the sigmoid chain can wash out the signal entirely.
Fix: functional probe (BLOCK simulation); if |phenotype shift| ≤ 0.05, add the latent gene
directly to a readout as a hidden confounder with weight ∈ [0.7, 1.5].

**Fix 5 — Phenotype bias re-centering**
Root cause: GRN dynamics converging to extreme gene expressions saturated the readout sigmoid
at 0 or 1. At saturation, individual knockouts are invisible → tasks appear additive, coverage low.
Fix: after all readout structure is finalised, set `bias = −Σ(w_i × baseline_expr_i)` so the
baseline phenotype = sigmoid(0) = 0.5. GRN dynamics unchanged.

### Verification results (`verify_organisms.py`, seeds 0–19)

| Tier | Before fixes | After fixes |
|------|-------------|-------------|
| Easy | 14/20 additive | 3/20 additive (near-linear dynamics — expected) |
| Medium | 7/20 additive | 1/20 |
| Hard | 4/20 additive + 5/20 latent-irrelevant | **0/20 flagged** |

Hard tier: all 20 seeds pass, latent gene relevance 1–5/5, gene coverage 0.60–1.00.

---

## 8. New Organism Stats (post PR #21, 2026-03-16)

Seeds 0–19 across all tiers. Computed from fixed generation code.

### Structure (constant by design)

| | Easy | Medium | Hard |
|---|---|---|---|
| Genes | 20 | 20 | 20 |
| Observable | 16 (80%) | 12 (60%) | 10 (50%) |
| Latent | 0 | 0 | 5 (25%) |
| Phenotypes | 3 | 3 | 3 |

### GRN complexity (varies by seed)

| | Easy | Medium | Hard |
|---|---|---|---|
| Relations | 26–42 (mean 34) | 57–75 (mean 67) | 87–121 (mean 102) |
| Gene coverage | 0.60–0.85 (mean 0.76) | 0.60–0.85 (mean 0.70) | 0.60–1.00 (mean 0.91) |

Edge count roughly triples easy → hard, reflecting higher intra/inter-module densities, more FFLs
and feedback loops.

### Task difficulty

| | Easy | Medium | Hard |
|---|---|---|---|
| Additive tasks (mean) | 0.8/2 | 0.3/2 | 0.0/2 |
| Mean max additive error | 0.167 ± 0.036 | 0.230 ± 0.056 | 0.330 ± 0.077 |
| Pass rate (verify_organisms) | 17/20 | 19/20 | 20/20 |

Additive error = gap between best linear prediction and ground truth — a proxy for nonlinearity.
Hard tier: zero additively solvable tasks, highest errors. Easy residual flags (3/20) are inherent
to near-linear sigmoid dynamics, not generation artefacts.

### Baseline phenotypes

All 180 phenotype values (20 seeds × 3 tiers × 3 phenotypes) = **exactly 0.500**.
Bias re-centering (step 13) is exact and deterministic: `bias = −Σ(w_i × baseline_expr_i)`.

### Hard tier: latent gene relevance

4–5/5 latent genes relevant per seed (mean 5.0/5). One borderline case (seed 13, 4/5) where one
gene's shift is just under the 0.05 threshold but it contributes at the readout level.

---

## 9. Canonical Benchmark Plan (Part 1)

### Design decisions

**n_genes = 20** — canonical design point. Tractable (budget=31 gives room for systematic
exploration + targeted follow-up) and discriminative (Claude vs GPT gaps confirmed at this size).
Scaling to larger networks is Part 2.

**Seeds** — selected via `select_seeds.py` (PR #25), which iterates from seed 0 and collects
the first N passing seeds per tier. Passing = no verification flags (structural, additivity,
latent relevance) + disease stability for medium. Selected seeds in `selected_seeds.json`.

**Two-step seed strategy**: run 10 seeds first. Extend to 20 if confidence intervals on hard or
disease are too wide. At std≈0.125, SE(n=10)=0.040 — sufficient to detect the ~0.15 Claude/GPT
gap on hard. Within-family comparisons (Sonnet vs Opus, ~0.04 gap) require n≈60; report those
with appropriate caveats.

**Disease tier = medium only** — disease mode adds task complexity (3 sub-tasks: predict +
diagnose + rescue) independent of organism topology. Running disease on hard would confound two
difficulty axes. The clean design: vary organism complexity on healthy (easy/medium/hard), vary
task complexity on medium (healthy vs disease). Hard disease would also worsen GPT context
exhaustion further.

### Organism reproducibility

Organisms are **re-generated on the fly** — not saved to disk. `generate_organism(seed,
difficulty)` is fully deterministic: seed + parameters → organism. The seed list in
`selected_seeds.json` *is* the dataset definition.

The risk is generation code changes invalidating results (as happened with PR #21). Guard:

- Generation code frozen at git tag **`v1-generation-freeze-2`** (commit `57f7be7`, 2026-03-17).
- All Part 1 runs must use this tag or a later commit that does not touch `lemonoids/generation.py`
  or `lemonoids/experiment.py`.
- Each results JSONL records the git commit hash at run time (via `run.py` metadata).
- If generation code must change before paper submission, re-run all sweeps and update the tag.

No organism serialisation is needed. If reviewers want to inspect specific organisms, they can
re-generate from seed + difficulty using the tagged code.

### Assumptions

| Assumption | Value | Rationale |
|---|---|---|
| n_genes | 20 | Tractable budget (31); discrimination confirmed |
| n_seeds (initial) | 10 | Sufficient for large Claude/GPT gap; extend to 20 if CIs too wide on hard/disease |
| Seed selection | `selected_seeds.json` | Pre-screened: healthy verified + disease stable |
| Disease tier | medium only | Isolates task complexity from organism complexity |
| Budget formula | n_genes + n_signals + 8 | Scales with organism; see §5 of benchmark_design.md |
| Noise | σ per tier (0.005/0.01/0.03) | Agent sees noisy measurements; scoring uses noiseless ground truth |
| Baselines | random + heuristic | random=floor, heuristic=non-LLM ceiling |

### Sweeps

| Sweep | Difficulty | Mode | Seeds | Status |
|---|---|---|---|---|
| A | medium | healthy | medium seeds from selected_seeds.json | pending |
| B | easy | healthy | easy seeds from selected_seeds.json | pending |
| C | hard | healthy | hard seeds from selected_seeds.json | pending |
| D | medium | disease | medium seeds from selected_seeds.json | pending |

### Models

| Model | Type | Notes |
|---|---|---|
| random | baseline | No experiments, predict 0.5 everywhere. Zero API cost. |
| heuristic | baseline | BLOCK sweep + additive prediction. Zero API cost. |
| claude-sonnet-4-6 | LLM | Run before Opus — cheaper, faster, catches bugs |
| claude-opus-4-6 | LLM | |
| gpt-4o | LLM | Most robust GPT model (18/20 valid in old disease sweep) |
| gpt-4.1 | LLM | |
| gpt-5.1 | LLM | Disease sweep: treat context failures as a finding (see §6) |

### Execution order

1. Run `random` + `heuristic` on all 4 sweeps — zero API cost, smoke-tests the pipeline.
2. Run `claude-sonnet-4-6` on all 4 sweeps.
3. Run `claude-opus-4-6` on all 4 sweeps.
4. Run GPT models (gpt-4o first as most stable, then gpt-4.1, then gpt-5.1).
5. If step-1 CIs look tight enough, stop at 10 seeds. Otherwise extend to 20.

### Metrics

Primary: composite score (mean ± std), valid N per sweep.
Secondary: prediction accuracy, MSE, budget utilisation fraction.
New (PR #23): network reconstruction F1 (undirected + directed gene→phenotype edges).
Disease breakdown: diagnosis score, rescue fraction, n_diagnosis_alternatives.

---

## 10. Scaling and Failure Mode Study (Part 2) — sketch

**Goal**: find where models collapse and characterise how they fail.

### Study 2a — n_genes scaling (new sweep)

Vary network size at fixed medium difficulty. Models: sonnet, heuristic, random (+ opus/gpt-4o
at n=80/160 for cross-family comparison). Seeds: 5–10 per n value.

| n_genes | Budget | Modules | Signals |
|---|---|---|---|
| 20 | 31 | 4 | 3 |
| 40 | 54 | 8 | 6 |
| 80 | 99 | 16 | 11 |
| 160 | 191 | 32 | 23 |

Expected: three regimes (ceiling / discriminative / collapse). Hypothesis: models reduce budget
utilisation as complexity grows past the optimum ("Illusion of Thinking" parallel).

### Study 2b — Budget efficiency (from Part 1 + 2a logs)

No new runs — computed from existing logs. Plot score vs budget fraction by model and difficulty.
Test whether models use *less* budget on hard organisms despite scoring worse.

### Study 2c — Failure mode taxonomy (qualitative)

Code ~20 hard + disease agent traces into failure categories:
`BUDGET_EXHAUSTED` / `PREMATURE_CONVERGENCE` / `SYSTEMATIC` / `THRASHING`.

### Study 2d — Network reconstruction vs prediction accuracy

Correlation between network F1 score and prediction accuracy across difficulty tiers. Tests
whether understanding the causal structure predicts scoring well.

---

## §10 Final Benchmark Results (2026-03-18, updated)

Full run complete: 7 models × 4 sweeps × 20 seeds = **560/560 sessions, all N=20**.
(5 LLMs + heuristic + random baselines.)
Generation frozen at `v1-generation-freeze-2` (commit `57f7be7`).

Fixes applied during this run:
- Early-stop bug fixed in `lemonoids/agent.py` (gpt-5.1/gpt-4.1 exiting before submitting; now nudged to complete).
- HTTP 500/529/503 overload retries added to `_with_retry` (opus disease seeds required up to 10 retry attempts each due to persistent API overloads on 2026-03-17/18).

### Composite Score (mean ± std, N=20 all)

| Model | Easy (healthy) | Med (healthy) | Hard (healthy) | Med (disease) |
|---|---|---|---|---|
| claude-opus-4-6   | **1.000** ± 0.000 | **0.967** ± 0.068 | **0.783** ± 0.172 | **0.833** ± 0.179 |
| claude-sonnet-4-6 | 0.983 ± 0.051 | 0.917 ± 0.101 | 0.733 ± 0.157 | 0.783 ± 0.178 |
| gpt-5.1           | 0.942 ± 0.082 | 0.850 ± 0.142 | 0.717 ± 0.188 | 0.582 ± 0.185 |
| gpt-4o            | 0.925 ± 0.085 | 0.783 ± 0.122 | 0.633 ± 0.159 | 0.481 ± 0.125 |
| gpt-4.1           | 0.900 ± 0.137 | 0.767 ± 0.126 | 0.592 ± 0.232 | 0.682 ± 0.146 |
| heuristic         | 0.775 ± 0.124 | 0.733 ± 0.100 | 0.342 ± 0.183 | 0.611 ± 0.212 |
| random            | 0.800 ± 0.103 | 0.750 ± 0.085 | 0.483 ± 0.142 | 0.492 ± 0.142 |

### Disease Mode Breakdown (medium, N=20 all)

| Model | Pred acc | Diagnosis | Rescue | Composite |
|---|---|---|---|---|
| claude-opus-4-6   | 0.900 | **0.600** | 1.000 | **0.833** |
| claude-sonnet-4-6 | 0.917 | 0.450 | 0.983 | 0.783 |
| gpt-4.1           | 0.817 | 0.050 | 0.300 | 0.682 |
| heuristic         | 0.650 | 0.350 | 0.833 | 0.611 |
| gpt-5.1           | 0.675 | 0.050 | 0.333 | 0.582 |
| random            | 0.692 | 0.050 | 0.733 | 0.492 |
| gpt-4o            | 0.567 | 0.050 | 0.717 | 0.481 |

### Key observations

- **Easy**: near-ceiling for all LLMs (0.90–1.00); weak discriminator.
- **Medium healthy**: clear Claude > GPT gap (0.92–0.97 vs 0.77–0.85). Random (0.750) ≈ heuristic (0.733) — heuristic adds little on medium.
- **Hard healthy**: sharpest discrimination. Heuristic (0.342) collapses *below* random (0.483) — systematic BLOCK sweep fails on high-feedback organisms. Claude holds ~0.73–0.78; GPTs drop to 0.59–0.72.
- **Disease diagnosis**: stark prediction/diagnosis dissociation in GPT models — gpt-5.1/gpt-4o/gpt-4.1 all score ~0.05 on diagnosis (≈ random) despite reasonable prediction accuracy. Claude opus leads (0.60), Claude sonnet second (0.45). Heuristic (0.35) beats all GPTs through exhaustive hypothesis enumeration.
- **gpt-4.1 disease composite (0.682) > gpt-4o (0.481)**: counterintuitive given gpt-4.1 < gpt-4o on all healthy sweeps. Root cause: gpt-4.1 has 11/20 seeds with budget_used=0 — it skips experiments entirely and submits predictions directly from the organism description, scoring pred_acc=0.667–1.000. gpt-4o actually runs experiments on most seeds but its predictions are worse (avg_acc=0.567), suggesting it gets confused by perturbation results. gpt-4.1 "laziness" is accidentally rewarded by the composite formula which weights prediction accuracy heavily even when diagnosis=0. Not a sign of better reasoning — rather a failure to engage with the task.
- **Heuristic (0.611) beats all GPTs on disease**: heuristic uses a fixed budget=21 for exhaustive hypothesis enumeration — it systematically tests blocking/locking each candidate gene and scores outcomes. This is effective abductive inference by exhaustion: 7/20 seeds get diag=1.0. GPTs almost never identify the correct malfunction (diag≈0.05 = 1/20 correct each). The heuristic's brute-force sweep is a stronger diagnosis strategy than language-based deduction for this task, suggesting GPT models are not doing genuine abductive reasoning over interventional evidence.

---

## §11 Deeper Analysis (2026-03-18)

Computed from session logs using `analyse.py`. All N=20 per model/sweep.

### §11.1 Complexity threshold — gradual degradation, not a cliff

Drop in composite score from easy → hard:

| Model | Easy→Hard drop | Hard std | Seeds≥0.80 | Seeds<0.50 |
|---|---|---|---|---|
| claude-opus-4-6   | −0.208 | 0.178 | 12/20 | 0/20 |
| claude-sonnet-4-6 | −0.258 | 0.165 | 10/20 | 0/20 |
| gpt-5.1           | −0.225 | 0.188 |  9/20 | 1/20 |
| gpt-4o            | −0.267 | 0.161 |  6/20 | 2/20 |
| gpt-4.1           | −0.308 | 0.232 |  4/20 | 3/20 |

Performance degrades gradually (no cliff), but high per-seed variance on hard suggests bimodal structure: models either solve an organism or partially fail — not graceful degradation within each seed. Claude never catastrophically fails on hard (0 seeds below 0.50); GPT-4.1 does (3/20).

### §11.2 Budget usage patterns

| Model | Easy | Med(H) | Hard | Med(D) |
|---|---|---|---|---|
| claude-opus-4-6   | 0.86±0.03 | 0.88±0.04 | 0.84±0.03 | 0.82±0.04 |
| claude-sonnet-4-6 | 0.80±0.04 | 0.81±0.03 | 0.76±0.03 | 0.75±0.05 |
| gpt-5.1           | 0.81±0.17 | 0.85±0.08 | 0.69±0.14 | 0.36±0.34 |
| gpt-4o            | 0.50±0.22 | 0.50±0.22 | 0.54±0.15 | 0.30±0.19 |
| gpt-4.1           | 0.67±0.13 | 0.63±0.19 | 0.60±0.15 | 0.28±0.35 |

Key findings:
- Claude uses budget consistently regardless of difficulty (~80–88%). No budget exhaustion.
- GPT-4o/4.1 use far less budget and are highly variable (large std).
- **Budget fraction does not correlate with composite score on hard** (r ≈ 0.0–0.2 per model). Failures are not caused by running out of budget — models stop early and still fail.
- **gpt-4.1 disease: 11/20 seeds with zero experiments** — model reads description and submits predictions without any perturbation experiments.

### §11.3 Disease mode — ambiguity and rescue

Diagnosis by n_diagnosis_alternatives:
- **n_alternatives=0** (unambiguous, 74/100 sessions): Opus 62.5%, Sonnet 40%, GPTs ~0–8%.
- **n_alternatives=1** (14 sessions): Opus 100%, Sonnet 50%, GPTs 0–33%.
- **n_alternatives≥2** (12 sessions): **nobody** gets it right across all models.

Rescue vs diagnosis:
- Correct diagnosis (N=22): rescue = 0.955
- Wrong diagnosis (N=78): rescue = 0.526
- Strong signal: diagnosis accuracy is the bottleneck for rescue performance. Models that fail to diagnose still partially rescue (~52%) — likely due to generic stabilising interventions.

### §11.4 Strategy analysis (medium healthy)

| Model | AvgExpts | BudgetFrac | SingleGene% | MultiGene% | Coverage% |
|---|---|---|---|---|---|
| claude-opus-4-6   | 27.2 | 0.88 | 98.5% |  1.5% | 100.0% |
| claude-sonnet-4-6 | 25.0 | 0.81 | 71.8% | 28.2% | 100.0% |
| gpt-5.1           | 26.6 | 0.85 | 64.8% |  0.2% |  55.5% |
| gpt-4o            | 12.8 | 0.50 | 10.0% |  0.0% |   2.3% |
| gpt-4.1           | 16.8 | 0.63 |  5.0% |  0.0% |   2.5% |

Key findings:
- **Claude Opus**: near-exhaustive single-gene BLOCK sweep (98.5%), tests all 20 genes (100% coverage). Highly systematic.
- **Claude Sonnet**: mixes single and multi-gene experiments (28% multi); still achieves full coverage. More exploratory.
- **gpt-5.1**: runs many experiments (26.6) but only covers 55% of genes — redundant experiments on a subset.
- **GPT-4o/4.1**: run few experiments, almost no single-gene sweeps, ~2% gene coverage — barely explore the organism at all.
- **Adaptive behaviour** (disease, re-testing genes): Claude 20/20 sessions, GPTs 0–1/20. Claude builds on earlier observations; GPTs do not.

### §11.5 Network reconstruction vs prediction accuracy

Pearson r(network_F1, prediction_accuracy) per model:

| Model | Medium r | Hard r | Medium NetF1 | Hard NetF1 |
|---|---|---|---|---|
| claude-opus-4-6   | +0.11 | +0.11 | 0.713 | 0.503 |
| claude-sonnet-4-6 | −0.43 | +0.23 | 0.753 | 0.544 |
| gpt-5.1           | −0.26 | +0.17 | 0.570 | 0.440 |
| gpt-4o            | +0.40 | +0.34 | 0.365 | 0.403 |
| gpt-4.1           | +0.58 | +0.40 | 0.308 | 0.375 |

Weak and inconsistent correlations overall. Building a correct causal map does not reliably predict prediction accuracy — models may succeed through pattern matching or baseline memorisation rather than genuine network inference. Claude has higher network F1 than GPTs despite the network not strongly predicting its scores, suggesting it infers better structure but the structure isn't the sole source of its prediction ability.

---

## Open Questions / Next Steps

- ~~**Run Part 1 sweeps**~~ — **DONE** (2026-03-17), 560/560 clean.
- ~~**Extend to 20 seeds?**~~ — **DONE**, ran 20 seeds throughout.
- ~~**gpt-5.1 disease diagnosis=0**~~ — **DONE** (2026-03-17): prediction/diagnosis dissociation confirmed — GPT models submit hypotheses but almost always wrong gene/type (diag≈0.05 ≈ random for gpt-5.1/4o/4.1). Write up as §5 failure mode analysis.
- ~~**gpt-4.1 disease composite anomaly**~~ — **DONE** (2026-03-18, §11.2): 11/20 zero-experiment seeds confirmed from logs.
- ~~**Budget patterns**~~ — **DONE** (2026-03-18, §11.2): no budget exhaustion; failures are early-stopping not running out of budget.
- ~~**Complexity threshold**~~ — **DONE** (2026-03-18, §11.1): gradual degradation, bimodal on hard, Claude never catastrophically fails.
- ~~**Ambiguity analysis**~~ — **DONE** (2026-03-18, §11.3): nobody solves ≥2-alternative organisms; Opus solves 100% of 1-alternative cases.
- ~~**Strategy analysis**~~ — **DONE** (2026-03-18, §11.4): Claude systematic BLOCK sweep + adaptive; GPTs low coverage, non-adaptive.
- **Heuristic beats GPTs on diagnosis**: worth a paragraph — exhaustive enumeration outperforms language-based abduction. Implication: GPT models are not doing genuine interventional reasoning for diagnosis.
- **Causal hypothesis quality** (§5): spot-check ~10 free-text hypotheses per model against ground truth — remaining Tier 3 analysis.
- **Dataset statistics table**: n_genes, n_phenotypes, n_prediction_tasks, n_diagnosis_alternatives per tier — compute from generation for paper §2.4.
- **Part 2 timing**: run 2a scaling sweep after Part 1 draft results are stable.
