# LEMONOIDS — Research Ideas & Experiment Log

A living document for research questions, experiment ideas, and observations.
Add freely — entries don't need to be complete or fully formed.

---

## Research Questions

_What do we want to learn from this benchmark?_

- **Optimal intervention policy / causal discovery efficiency**: connects to active causal
  learning (Hauser & Bühlmann 2012, Murphy 2001). BLOCK = hard do-calculus intervention,
  theoretically optimal for revealing downstream dependencies. Adaptive strategies
  exponentially outperform non-adaptive. With module structure, optimal policy is BLOCK one
  gene per module first, then drill. At N=1280 with B≈1471, information-theoretic lower bound
  suggests near-complete edge identification is achievable under sparsity — consistent with
  Sonnet's near-perfect scores. Framing: Sonnet has implicitly learned a near-optimal policy;
  GPT-4o has not. Implementation: compute theoretical lower bound on genes-to-perturb for
  observed prediction accuracy, compare against actual coverage as an "efficiency" metric.

- **Threshold sensitivity analysis**: does the Claude > GPT performance gap hold at tighter
  prediction accuracy thresholds (±0.08, ±0.07)? Current ±0.10 was chosen empirically because it
  correctly exposes baselines as near-chance on hard (±0.15 inflated them), but the justification
  is partly circular. Now computable post-hoc from logs (per-phenotype ground_truth/prediction
  stored after PR #39) — no re-run needed. Key question: is the gap a robust finding or
  threshold-dependent? Also worth checking relation to noise floor: σ=0.01 medium, 0.03 hard.

- **Experimental bias / noisy readouts**: not all phenotype readouts may be true readouts — some
  could be indirect, noisy, or conditionally observable. How does this affect agent strategy and
  scoring? Could be modelled as readout noise, partial observability of phenotypes, or "false"
  readout channels that correlate but don't causally depend on the network.

- **Visualisation scaling**: the inspector CLI works well for 15-gene medium organisms, but will
  the GRN graph and terminal tables degrade gracefully for large/complex organisms (e.g. hard tier,
  40+ genes)? Worth stress-testing and possibly adding layout heuristics or collapsed views.

- **Knowledge vs. brute force**: Do agents form genuine causal models of the network, or just
  collect data points? Brute-force BLOCK/BOOST of all genes fails on complex organisms (budget
  exhausted, latent genes, dense feedback). A successful agent needs an internal model.
  Key question: can we measure *what the agent knows* about the network, not just whether it
  succeeds at the task?

- **Intervention type preferences**: do agents show a systematic preference for BLOCK vs BOOST vs DAMPEN?
  Hypothesis: BLOCK dominates early (network discovery — silences a gene, reveals dependencies); BOOST/DAMPEN
  appear later as hypothesis-testing moves. Opus healthy data already suggests near-exclusive BLOCK use.
  Interesting follow-up: does BOOST/DAMPEN usage correlate with higher diagnosis accuracy in disease mode
  (i.e. does targeted hypothesis-testing help)? Computable from existing session logs.

- **Budget allocation timing**: at what experiment index does each model call `get_next_prediction_task()`?
  Does submitting predictions earlier (less discovery) correlate with lower accuracy? Opus uses ~88% of
  budget before predicting; GPT-4o stops at ~50%. Computable from existing session logs (look for
  `get_next_prediction_task` tool calls and their experiment_idx at time of call). Could disentangle
  whether the Opus/GPT gap is explained by discovery depth vs. reasoning quality.

- **Knowledge vs. retrieval via gene naming**: genes are currently opaque IDs (G001, G002...)
  preventing retrieval shortcuts. Two testable variants: (1) invented-but-suggestive names
  (e.g. `repressor-alpha`, `flux-gate-3`) — agents can form functional priors but can't look
  anything up; (2) real biology names (TP53, BRCA1, etc.) mapped onto the synthetic GRN —
  directly measures how much retrieval from training data helps or hurts (wrong priors on a
  synthetic network). Gap between opaque vs. named conditions isolates knowledge retrieval from
  causal reasoning. Natural Part 3 extension; requires only a vocabulary swap in generation.

- **Context efficiency as a first-class metric**: measure how agents use their context window —
  tool calls per turn, total tokens consumed, redundant experiments (re-perturbing a gene already
  observed), and information gained per budget unit. Motivated by gpt-5.1 disease failures: a
  model that exhausts context before finishing is qualitatively different from one that predicts
  wrong. Could also reveal whether Claude's lower batching rate reflects a deliberate strategy
  or just a stylistic difference. Computable from existing JSON session logs.

---

## Figure Ideas

_Additional figures for the paper, to be implemented in the paper repo._

- **Difficulty scaling line plot**: performance (composite score) vs difficulty tier
  (easy → medium → hard) as a line per model. Drives home the discrimination point more
  viscerally than the heatmap — shows Claude's robustness vs GPT degradation as slope.
  Both healthy and disease modes could be overlaid or shown as separate panels.

- **Disease component radar/spider**: pred_acc / diagnosis / rescue as a radar chart per
  model (medium disease). Visually captures the rescue-without-diagnosis dissociation —
  the asymmetry between high rescue and low diagnosis is immediately apparent in polar
  coordinates.

---

## Experiment Ideas

_Concrete things to run. Include model, difficulty, mode, and what we expect to see._

- **Probe questions** (knowledge eval): after a session ends, ask the agent targeted questions
  about the network ("which gene most strongly drives phenotype X?", "are G010 and G016 in the
  same pathway?") and score against ground truth `gene_phenotype_edges` already stored in the
  session log. Cleanly separates *knowing the network* from *succeeding at the task*.
  Extension: ask the agent to reconstruct the full adjacency matrix / edge list and compute
  precision/recall against ground truth. Stronger test than probe questions — requires a coherent
  internal model, not just correct answers to specific queries.

- **Full adjacency matrix reconstruction** (offline, no API needed): current network analysis
  only scores gene→phenotype edges. Gene→gene edges are not stored in session logs (experiment
  results record phenotype values only, not gene states). Re-simulate each perturbation from
  frozen organisms (generation freeze `v1-generation-freeze-2`) to get gene state shifts, then
  compare agent-inferred edges (from hypothesis text) against the full ground truth adjacency
  matrix. Stronger test than phenotype-edge F1 — requires a coherent internal GRN model.
  Directly addresses the §6 finding that network F1 doesn't predict performance.

- **Transfer tasks**: run an agent on a healthy organism, then immediately run it on the disease
  version of the same organism. Does prior knowledge help diagnosis speed and accuracy?

- **Hypothesis scoring**: parse `submit_hypothesis` free text and compare stated gene→phenotype
  edges against ground truth. Needs an LLM-as-judge or structured hypothesis format.

- **Non-LLM baselines**: implement classic perturbation-based prediction methods as baselines
  (e.g. nearest-neighbour in intervention space, linear regression from observed perturbations,
  random forest). Should live alongside `--heuristic` in `evaluate.py`. Gives a lower bound on
  what structured search buys vs. pure statistical pattern matching.

- **Gene coverage as scaling metric** (post-hoc, no re-run): fraction of unique genes perturbed
  at least once / total genes in organism. Distinct from redundancy (re-perturbations/total).
  At N=1280 with budget ~1471, coverage must drop below 100% — if coverage correlates with score
  this is the "exploration bottleneck" story. Computable from existing scaling_v1 session logs.

- **Ablation: remove sources of hardness** — run medium difficulty with (a) `feedback_fraction=0`
  and (b) `latent_fraction=0`, keeping all else equal. Generation already supports these params.
  Show whether heuristic improves and whether LLMs improve differently. Cleanly isolates what
  makes the task hard structurally. Run heuristic first (free), then LLMs if interesting.

- **Budget scaling** — fix N (e.g. N=80 or N=160), vary budget at 0.5×, 1×, 2× the default.
  Tests whether models are strategy-limited vs compute-limited: if 2× budget doesn't improve
  score, the bottleneck is reasoning quality not exploration depth. Clean experiment, very
  defensible to reviewers. Needs small `run.py` extension to override budget formula.

- **Ambiguity vs diagnosis accuracy** (post-hoc, no re-run): `n_diagnosis_alternatives` is
  already stored in Part 1 disease session logs. Plot x=ambiguity (number of plausible
  malfunctions), y=diagnosis accuracy. Expect a sharp drop at high ambiguity. Connects to
  identifiability theory and causal inference. Free to compute from existing results.

---

## Observations

_Things noticed during test drives, agent sessions, or data exploration worth following up._

- **GPT models fail on specific seeds due to context exhaustion**: GPT models (4o, 4.1, 5.1)
  batch tool calls aggressively (5–10 per turn vs Claude's 2–3), generating large tool result
  messages that fill the context window on verbose organisms. Disease mode is worse — larger
  tool schema + longer system prompt + extra tasks. Same seeds tend to fail across GPT models
  (e.g. seed 14) because organism topology determines response verbosity, not model randomness.
  For the paper: report as a failure mode; note that Claude's conservative batching is implicitly
  more context-efficient. Potential fix: add per-turn experiment count guidance to the system prompt.

---

## Friction / Usability Issues

_Rough edges found during test drives. Move to GitHub issues once confirmed._

- **Parallelisation for experiment runs**: models currently run sequentially within a sweep
  (~2–3h per model × 5 models = 10–15h per sweep). Two natural levels: (1) run models in
  parallel using `concurrent.futures.ProcessPoolExecutor` or separate shell processes;
  (2) run seeds in parallel within a model using async API clients. Rate limits are the
  main constraint — start with model-level parallelism (safe, independent) before seed-level.

- **HTML trace reports**: currently only JSONL results are saved; individual agent behaviour
  requires parsing raw JSON logs. Add per-session HTML reports showing agent turns, experiments
  run, predictions submitted, and per-task scores in a readable, self-contained file.
  Could be generated by `run_agent()` alongside the existing `log_path` JSON trace.
