# LEMONOIDS — Research Ideas & Experiment Log

A living document for research questions, experiment ideas, and observations.
Add freely — entries don't need to be complete or fully formed.

---

## Research Questions

_What do we want to learn from this benchmark?_

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

- **Context efficiency as a first-class metric**: measure how agents use their context window —
  tool calls per turn, total tokens consumed, redundant experiments (re-perturbing a gene already
  observed), and information gained per budget unit. Motivated by gpt-5.1 disease failures: a
  model that exhausts context before finishing is qualitatively different from one that predicts
  wrong. Could also reveal whether Claude's lower batching rate reflects a deliberate strategy
  or just a stylistic difference. Computable from existing JSON session logs.

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

- **Transfer tasks**: run an agent on a healthy organism, then immediately run it on the disease
  version of the same organism. Does prior knowledge help diagnosis speed and accuracy?

- **Hypothesis scoring**: parse `submit_hypothesis` free text and compare stated gene→phenotype
  edges against ground truth. Needs an LLM-as-judge or structured hypothesis format.

- **Non-LLM baselines**: implement classic perturbation-based prediction methods as baselines
  (e.g. nearest-neighbour in intervention space, linear regression from observed perturbations,
  random forest). Should live alongside `--heuristic` in `evaluate.py`. Gives a lower bound on
  what structured search buys vs. pure statistical pattern matching.

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

- **seed=14 disease always fails**: `generate_disease_organism(seed=14, difficulty=medium)` raises
  `RuntimeError` consistently across all models — the network is too stable and no malfunction
  produces aberrant phenotypes after 10 generation attempts. Options: (a) exclude seed 14 from
  disease sweeps and document it, or (b) replace with seed 20 to keep N=20. Affects all disease
  results (19/20 seeds succeed). Address before paper submission.

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
