# LUCA — Research Ideas & Experiment Log

A living document for research questions, experiment ideas, and observations.
Add freely — entries don't need to be complete or fully formed.

---

## Paper-strengthening (current submission)

_Ideas that can be executed with little or no new runs — computable from existing logs or cheap to run._

- **Threshold sensitivity analysis**: does the Claude > GPT performance gap hold at tighter
  prediction accuracy thresholds (±0.08, ±0.07)? The ±0.10 choice was empirically motivated;
  a robustness check strengthens the claim. Fully computable post-hoc from session logs
  (per-phenotype ground_truth/prediction stored after PR #39) — no re-run needed. Also worth
  checking against the noise floor: σ=0.01 medium, 0.03 hard.

- **Ambiguity vs diagnosis accuracy** (post-hoc, no re-run): `n_diagnosis_alternatives` is
  stored in Part 1 disease session logs. Plot x=ambiguity (0, 1, ≥2 alternative malfunctions),
  y=diagnosis accuracy. LAB_JOURNAL §11.3 already shows the breakdown: unambiguous (74/100
  sessions) vs 1-alternative vs ≥2-alternative. Clean identifiability story; goes in the
  disease mode analysis section or appendix.

- **Causal discovery efficiency framing**: re-frame the existing strategy analysis data
  (LAB_JOURNAL §11.4, `strategy_analysis.jsonl`) in terms of active causal learning theory
  (Hauser & Bühlmann 2012, Murphy 2001). BLOCK = hard do-calculus intervention, theoretically
  optimal for revealing downstream dependencies. Opus achieves 100% gene coverage with 98.5%
  single-gene experiments; GPT-4o/4.1 cover ~2% of genes. Framing: Sonnet/Opus have implicitly
  learned a near-optimal discovery policy; GPTs have not. Could compute theoretical lower bound
  on experiments-to-cover as a baseline comparison.

- **Budget allocation timing** (post-hoc, no re-run): at what experiment index does each model
  call `get_next_prediction_task()`? Does submitting predictions earlier correlate with lower
  accuracy? Opus uses ~88% of budget before predicting; GPT-4o stops at ~50%. Computable from
  existing session logs. Could disentangle whether the Opus/GPT gap is explained by exploration
  depth vs. reasoning quality at prediction time.

- **Ablation: remove sources of hardness** — run medium difficulty with (a) `feedback_fraction=0`
  and (b) `latent_fraction=0`, keeping all else equal. Generation already supports these params.
  Show whether heuristic improves and whether LLMs improve differently — directly isolates what
  makes the task structurally hard. Run heuristic first (free, no API key), then LLMs if result
  is interesting.

- **Context efficiency metric**: model token consumption is already logged. Formalise as a
  metric: total tokens per session, tool calls per turn, redundant experiments (re-perturbing
  an already-tested gene), and information gained per budget unit. Computable from existing JSON
  session logs. Strengthens the GPT context exhaustion finding by quantifying it rather than
  just noting it as a failure mode.

- **Open-source model results subsection**: DeepSeek V3.1 and Qwen 3.5 match Claude on
  prediction accuracy (0.91, 0.89 vs Opus 0.90 on medium healthy) but not on causal diagnosis
  (0.10–0.24 vs Opus 0.55 on medium disease). The rescue-without-diagnosis dissociation is now
  universal across 3 model families (Claude, GPT, open-source), not GPT-specific. Paper addition:
  short Results subsection, extend existing tables, note the diagnosis gap as the clearest
  capability separation. Cost footnote: full open-source run was ~$30 vs hundreds for
  proprietary models.

---

## Figure Ideas

_Additional figures for the paper — implement in the paper repo._

- **Difficulty scaling line plot**: composite score vs difficulty tier (easy → medium → hard)
  as a line per model. Drives home the discrimination point more viscerally than the heatmap —
  shows Claude's robustness vs GPT degradation as slope. Both healthy and disease modes could
  be overlaid or shown as separate panels.

- **Disease component radar/spider**: pred_acc / diagnosis / rescue as a radar chart per model
  (medium disease). Visually captures the rescue-without-diagnosis dissociation — the asymmetry
  between high rescue and low diagnosis is immediately apparent in polar coordinates.

---

## Conflict-of-Interest Controls

_Addresses the concern that the benchmark was authored using Claude Code and may inadvertently favour Claude's reasoning style. Two distinct sub-questions; both deferred until after initial submission._

- **Gemini as benchmark agent** (quantitative): run the full Part 1 sweep (or at minimum
  `A_medium_healthy`, 20 seeds) with `gemini-2.5-pro` or `gemini-2.0-flash` as the agent.
  If Gemini scores in a pattern consistent with the task requiring genuine causal reasoning
  (e.g. scores correlate with difficulty tier, not with model family), it strengthens the
  claim that the benchmark is not biased toward Claude's prompt style.
  Implementation: add Gemini as a native provider in `luca/agent.py` using the
  OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`)
  with the existing `openai` SDK — no new dependency needed. Needs `GEMINI_API_KEY` in `.env`.
  See plan file for full implementation notes.

- **Gemini as design auditor** (qualitative): feed Gemini the system prompt, tool descriptions,
  and 2–3 session logs (one Claude, one GPT, one heuristic) and ask it to identify any
  structural biases in the task framing, scoring, or prompt language that might favour a
  particular model family. This is a qualitative audit, not a scored experiment. Could be run
  as a one-off before submission and summarised in a sentence in the paper or supplementary.

---

## Extension Directions

_For future work sections or follow-on papers. Not needed for this submission._

- **Backwards organisms (structural prior control)**: invert all edge signs in the GRN
  (activations → inhibitions and vice versa, plus sign-flip on biases to maintain baseline ≈ 0.5)
  to create organisms whose dynamics systematically violate the structural intuitions a model
  might have learned from real GRN literature. A model doing genuine causal inference from
  perturbation experiments should score equally well on backwards organisms — it observes the
  actual dynamics and updates regardless of prior expectations. A model anchoring on structural
  priors (e.g. "blocking an activator reduces downstream") would be systematically wrong.
  **What to measure**: score gap between normal and backwards organisms, per model. Claude gap ≈ 0,
  GPT gap > 0 would be strong evidence that Claude's advantage reflects genuine inference rather
  than transferred heuristics.
  **Implementation**: generation-level parameter (invert edge weight signs post-sampling, re-center
  phenotype biases). No new experiment infrastructure needed. Minimum sweep: A_medium_healthy,
  20 seeds × 5 models. Pairs cleanly with the existing benchmark as a matched within-organism
  comparison if the same seeds are used.
  **Note**: inhibitory edges already exist (30–40% inhibition fraction), so a partial inversion
  isn't novel enough — full inversion of all signs is needed to truly violate structural priors.

- **Knowledge vs. retrieval via gene naming**: two testable variants beyond opaque IDs (G001,
  G002...): (1) invented-but-suggestive names (`repressor-alpha`, `flux-gate-3`) — agents form
  functional priors but can't look anything up; (2) real biology names (TP53, BRCA1) mapped onto
  the synthetic GRN — directly measures how much retrieval from training data helps or hurts on
  a network with no relation to real biology. Gap between conditions isolates retrieval from
  causal reasoning. Requires only a vocabulary swap in generation.

- **Part 3: prior knowledge integration** — full design in `docs/designs/part3_knowledge_extension.md`.
  Hypothesis: synthetic "organism family datasheets" help most exactly above the complexity
  threshold where pure causal reasoning fails. 2×2 design (no-knowledge/knowledge ×
  below-threshold/above-threshold).

- **Non-LLM baselines**: implement perturbation-based ML baselines alongside `--heuristic`
  in `evaluate.py` (e.g. linear regression from observed perturbations, nearest-neighbour in
  intervention space, random forest). Gives a lower bound on what structured search buys vs.
  pure statistical pattern matching.

- **Exploration vs reasoning — three-level decomposition**: the benchmark separates three
  capability levels: (1) *exploration quality* — choosing which experiments to run (budget
  usage, gene coverage; all capable models solve this); (2) *functional approximation* —
  predicting outcomes using the right mathematical model of the readout (info-bandit's
  logit trick matches LLMs on medium prediction without any causal model); (3) *causal
  reasoning* — building a structural model to handle feedback loops (hard-tier prediction)
  and abductive inference (diagnosis). The key finding: LLMs add value primarily at level 3.
  Levels 1–2 are solvable by algorithmic baselines. This reframes the paper narrative from
  "LLMs are better" to "the benchmark pinpoints where LLM reasoning adds value beyond
  algorithmic approaches." Diagnosis is the clearest level-3 task — no algorithmic baseline
  approaches Claude's 0.55. Hard-tier prediction is the second — feedback loops violate the
  independence assumptions that make logit combination work.

- **Algorithmic experimental design baselines**: the info-bandit baseline (PR #49) scores
  0.883 on medium healthy using logit-space prediction — matching Sonnet (0.875) without any
  LLM. This suggests the prediction gap between additive heuristic (0.575) and LLMs is largely
  explained by handling sigmoid nonlinearity, not sophisticated reasoning. LLMs use brute-force
  BLOCK sweeps; established approaches from active learning, Bayesian experimental design, and
  causal discovery (UCB, Thompson sampling, D-optimal design, information-theoretic criteria)
  could match or exceed LLM prediction with far fewer experiments. The contrast — LLMs succeed
  by exploring broadly, algorithmic baselines by exploring efficiently — reframes the benchmark:
  it measures exploration strategy quality, not just reasoning ability. Concrete next step: run
  info-bandit on all 6 sweeps + hard tier to see where algorithmic prediction breaks down
  (likely hard, where feedback loops violate the independence assumption in logit combination).

- **Transfer tasks**: run an agent on a healthy organism, then immediately on the disease version
  of the same organism. Does prior knowledge of the network accelerate diagnosis?

- **Budget scaling**: fix N (e.g. N=80), vary budget at 0.5×, 1×, 2× default. Tests whether
  models are strategy-limited vs. compute-limited: if 2× budget doesn't improve score, the
  bottleneck is reasoning quality not exploration depth.

- **Probe questions / structured knowledge eval**: after a session ends, ask targeted questions
  about the network ("which gene most strongly drives phenotype X?", "are G010 and G016 in the
  same module?") and score against ground truth. Cleanly separates knowing the network from
  succeeding at the task. Could extend to full adjacency matrix reconstruction to evaluate
  inferred gene→gene edges against ground truth.
