# LUCA — Design Decisions

A record of significant design choices: what was decided, why, and what was rejected.
Add entries here when a non-obvious decision is made that future contributors would wonder about.

---

## Benchmark Design

### Invented vocabulary (no real biology terms)
**Decision:** All gene names, module names, phenotypes, and cell types are invented nonsense words.
**Why:** Eliminates the retrieval confound — a model that has memorised biology textbooks cannot
"cheat" by pattern-matching gene names to known pathways. Any score reflects genuine causal
reasoning from perturbation data, not prior knowledge.
**Rejected:** Using real (but obscure) organism biology — too hard to guarantee no prior knowledge
exists in training data; invented vocabulary is the only watertight solution.

### GRN dynamics model
**Decision:** Sigmoid update rule, discrete-time synchronous update, steady-state readout.
**Why:** Simple enough to be tractable (agents can reason about it), complex enough to produce
non-trivial causal structure (FFLs, feedback loops, latent genes). Grounded in the literature
(Mjolsness et al. 1991; Karlebach & Shamir 2008).
**Rejected:** Continuous ODE dynamics — too slow to simulate at scale and harder for agents
to reason about explicitly.

### Difficulty tiers (easy / medium / hard)
**Decision:** Four axes scaled by fractions: observability, FFL density, feedback density, latent genes.
**Why:** Fraction-based scaling ensures difficulty is consistent across different organism sizes.
Each axis contributes independently — easy organisms have high observability + low feedback;
hard organisms have latent genes + high feedback density.
**Rejected:** Single difficulty axis — doesn't capture the distinct challenges of partial
observability vs feedback complexity.

### Prediction task non-triviality guarantee
**Decision:** Each prediction task requires ≥0.1 phenotype shift from baseline.
**Why:** Without this, many tasks are trivially solved by predicting the baseline value.
The guarantee ensures every task requires genuine understanding of intervention effects.

### Budget design
**Decision:** Budget = number of `run_experiment()` calls allowed (not tokens or time).
**Why:** Makes the resource constraint explicit and model-agnostic. Agents must decide which
experiments are most informative — this is the core reasoning challenge.
Formula: `n_genes + n_signals + 8`. At n=20 this gives budget=31 for all difficulty tiers
(easy/medium/hard share the same n_genes and n_signals at the canonical design point).
The budget is not tighter on hard — hard is harder because of network topology (more feedback,
latent genes, nonlinearity), not because budget is reduced. The `+8` provides headroom for
follow-up experiments beyond a full single-element sweep.

---

## Disease Mode

### Hypothesis locking on first call
**Decision:** `submit_malfunction_hypothesis()` locks the hypothesis; can only be submitted once.
Score withheld until `get_summary()`.
**Why:** Prevents iterative guess-and-check on the diagnosis. Forces commitment — mirrors real
diagnostic settings where you act on your best hypothesis.

### Malfunction types: LOCK_HI / LOCK_LO / PERSIST
**Decision:** Three types of gene malfunction, selected from genes with non-trivial phenotype effects.
**Why:** LOCK_HI/LO model constitutive activation/silencing (common disease mechanisms).
PERSIST models failure of a gene to respond to upstream signals (e.g. receptor insensitivity).
Together they cover the main classes of regulatory dysfunction without being too domain-specific.

### Diagnosis scoring: exact / partial / wrong (1.0 / 0.5 / 0.0)
**Decision:** Partial credit (0.5) for correct gene but wrong malfunction type.
**Why:** Identifying the right gene is the hard part (abductive reasoning over many candidates).
Getting the type wrong is a softer error — the agent found the right locus but mischaracterised
the mechanism. Partial credit distinguishes these failure modes.

### n_diagnosis_alternatives
**Decision:** Track how many genes produce equivalent phenotype aberrations as a difficulty axis.
**Why:** Some organisms have unambiguous malfunctions (only one gene could cause the observed
pattern); others have 2–3 equally plausible candidates. This is a natural source of difficulty
variation beyond the healthy-mode complexity tiers.

---

## Reproducibility

### sorted() instead of list(set()) for gene ordering
**Decision:** All places where sets of genes are converted to lists use `sorted()`.
**Why:** Python's hash randomisation (`PYTHONHASHSEED`) makes `list(set)` non-deterministic
across processes. This caused `generate_disease_organism` to select different malfunctions for
the same seed when run in different processes — discovered 2026-03-17, fixed in PR #28.
**Rule:** Never use `list(set(...))` on gene collections in generation or experiment code.

### Generation freeze tags
**Decision:** Git tags mark canonical generation versions used for paper results.
- `v1-generation-freeze` — initial freeze (invalidated by organism quality fixes in PR #21)
- `v1-generation-freeze-2` (commit `8880d24`) — current canonical version; all paper v1 results use this
**Why:** Ensures results are reproducible even if generation code changes later.
**Note on references:** commit hashes throughout this repository resolve here; PR
numbers refer to pull requests in the private development repository and cannot be
opened from outside. The tags are the reliable handle for reproducing a result.

### 20 seeds per sweep
**Decision:** 20 seeds per model × sweep combination.
**Why:** Enough for stable mean/std estimates; small enough to be feasible with API costs.
Seed indices 0–19. Seeds are pre-screened to ensure disease organisms are valid (rescuable,
aberrant phenotypes detectable).

---

## Scoring & Metrics

### Composite score formula
**Decision:** Healthy mode: composite = prediction accuracy. Disease mode: mean(pred_acc, diag, rescue).
**Why:** Prediction accuracy is the primary signal in healthy mode (no diagnosis task).
In disease mode, equal weighting across three tasks reflects that each is a distinct capability
(forward simulation, abductive diagnosis, intervention planning). Equal weights chosen over
task-specific weights to avoid tuning decisions that would need justification.
**Known issue:** Equal weighting means partial task completion (e.g. submitting predictions but
not hypothesis) still scores non-zero. gpt-4.1 disease composite (0.567) is inflated by this —
some seeds skip experiments entirely and submit predictions from description alone, which scores
on pred_acc but 0 on diagnosis/rescue.
**Decision (2026-03-31):** Report pred_acc, diagnosis, and rescue as primary metrics in all
disease mode results tables; composite is a summary convenience only. This makes partial-task
inflation transparent and lets readers assess each capability independently. The sub-scores are
already computed and stored in all session logs — no re-runs needed.

### Prediction accuracy threshold (±0.10)
**Decision:** A prediction is "correct" if within 0.10 of the true phenotype value.
**Why:** Phenotypes are in [0,1]; ±0.10 is 10% of the full range. At ±0.15 the heuristic and
random baselines scored artificially high on hard organisms (masking the Claude > GPT gap).
Tightening to ±0.10 correctly exposes both baselines as near-chance on hard, validating that
hard organisms require genuine causal reasoning. Changed from ±0.15 in PR #36.

---

## Infrastructure

### Result files: local only, not in git
**Decision:** `.jsonl` result files are gitignored; only scripts and `.md` conclusions are committed.
**Why:** Results are regeneratable from scripts + seeds. Committing them bloats the repo,
creates noisy diffs, and gives false assurance (the code is the ground truth, not the outputs).
Conclusions are reported in the paper.

### Retry logic for API overloads
**Decision:** `_with_retry()` retries on HTTP 500/503/529 with exponential backoff (15s×attempt,
up to 6 attempts).
**Why:** Anthropic API returns 529 (overloaded) transiently, especially under heavy load.
Without retries, entire seeds fail and require manual re-runs. Added 2026-03-18 after the
opus disease sweep lost 18/20 seeds to overload errors overnight.

---

## Baselines

### Heuristic: exhaustive BLOCK sweep
**Decision:** Heuristic baseline systematically BLOCKs each observable gene one at a time
and uses additive prediction. At n=20 medium (12 observable genes + 3 signals + some
disease hypothesis probes), it uses approximately 15–21 experiments — well under the
budget=31 ceiling. It does not adapt its experiment count to the budget.
**Why:** Represents a principled non-LLM strategy — exhaustive enumeration rather than targeted
reasoning. Its performance sets a floor: anything a model achieves beyond this requires
genuine causal reasoning, not just systematic search.
**Interesting finding:** Heuristic collapses below random on hard organisms — systematic BLOCK
sweeps fail on high-feedback organisms where single-gene perturbations are dominated by feedback
effects. On medium disease, heuristic diagnosis = 0.100, below gpt-5.1 (0.200) and gpt-4.1
(0.167) — exhaustive enumeration is insufficient when signal malfunctions introduce ambiguity
that gene-level enumeration cannot resolve. (An earlier run recorded 0.35; superseded by the
final run with corrected seed exclusions.)

### Random baseline
**Decision:** Predicts 0.5 everywhere, runs zero experiments, submits random hypothesis.
**Why:** Lower bound. Any model that can't beat random on prediction has learned nothing from
perturbation data. The random baseline scores surprisingly well on easy organisms (~0.80
composite) because easy organisms have predictable dynamics — this confirms easy is a weak
discriminator.

### None=0 scoring for unattempted disease tasks (2026-04-09)
**Decision:** When a model does not call `submit_malfunction_hypothesis` or `test_rescue`,
the diagnosis score and rescue fraction are treated as 0, not excluded from the mean.
This is consistent with `evaluate.py` (`_composite_score` treats None as 0.0).
**Why:** Not attempting a task is a failure mode, not missing data. GPT-5.1 and GPT-4.1
frequently exhaust their context window before reaching the diagnosis/rescue phase
(attempt rates as low as 20–60%). Excluding these sessions would inflate their scores
and hide the context exhaustion failure. The attempt rate is reported separately for transparency.
**Rejected alternative:** Mean-over-submitted (only count sessions where the model tried).
This was used in an earlier draft of the results write-up and produced misleadingly high
GPT rescue scores (e.g. GPT-4.1 medium rescue 0.967 over 10 attempts vs 0.483 over 20 seeds).
The composite column was always computed with None=0, creating an internal inconsistency.
Corrected 2026-04-09.

### CausalSweep as a calibration baseline, not a fair competitor (2026-04-17)
**Decision:** CausalSweep is included in all tables alongside LLMs and other baselines,
but explicitly labelled as a "calibration baseline" that uses privileged knowledge.
**Why:** CausalSweep's logit-space prediction formula is derived from the sigmoid readout
function in `generation.py`. LLM agents do not have access to this — the system prompt
describes organisms abstractly without revealing the dynamics model. CausalSweep therefore
has an unfair advantage on prediction: it uses the mathematically correct formula while
LLMs must infer the dynamics from observations. Including it calibrates what "correct math
+ systematic experimentation" achieves without reasoning, making the LLM contribution
precise: LLMs add value on hard organisms (feedback loops break the independence assumption
in logit-combine), disease diagnosis (abductive inference from aberrant phenotypes), and
large-N exploration (adaptive strategy that scales beyond full-coverage BLOCK+BOOST sweeps).
**For the paper:** The privileged knowledge must be disclosed prominently — in the baselines
description, in the CausalSweep analysis paragraph, and in the figure captions. Reviewers
will ask "is this a fair comparison?" The answer is: it's not meant to be fair, it's meant
to be informative about what the benchmark actually measures.
**Rejected alternative:** Excluding CausalSweep from the paper entirely. This would leave
the impression that LLMs' prediction advantage reflects reasoning, when in fact it largely
reflects having the right mathematical model implicitly. Including CausalSweep is more
honest and makes the paper's claims more precise.
