# LEMONOIDS — Paper Outline

**Target venue:** NeurIPS (Datasets & Benchmarks track, or main track depending on Part 2 results)
**Working title:** *LEMONOIDS: A Synthetic Organism Reasoning Benchmark for LLM Agents*

---

## framing

The core claim: current LLM benchmarks conflate *retrieval* with *reasoning*. A model that has memorised biology textbooks will score well on biology tasks — but does it actually reason causally? LEMONOIDS removes retrieval entirely (invented vocabulary, no real gene names) and forces models to build causal models from perturbation experiments under budget constraints. It is a benchmark for *causal reasoning under uncertainty*, not knowledge recall.

Closest related venues of interest:
- NeurIPS D&B track — primary target for Part 1
- NeurIPS main track — if Part 2 produces strong mechanistic findings
- ICLR — if framing shifts toward agent evaluation / tool use

---

## Part 1 — Benchmark design + essential experiments
*Minimal publishable unit. Self-contained.*

### 1. Introduction
- LLMs are increasingly deployed as reasoning agents in science
- Existing benchmarks: knowledge retrieval, math, code — not causal reasoning from data
- The retrieval confound: models with biological priors can "cheat" on biology benchmarks
- LEMONOIDS: a benchmark that is *unknowable via retrieval* by construction
- Contributions: benchmark design, complexity tiers, disease mode, baseline results

### 2. Related work
- Scientific reasoning benchmarks (GPQA, SciEval, LAB-Bench, etc.)
- Agent benchmarks with tool use (SWE-bench, WebArena, etc.)
- Causal reasoning benchmarks (CausalBench, etc.)
- Perturbation-based biology (CRISPR screens, drug response) — motivation, not prior work
- Key gap: no benchmark isolates causal reasoning from retrieval in a controlled, scalable way

### 3. Benchmark design
#### 3.1 Organism model
- GRN dynamics: sigmoid update rule, citation (Mjolsness et al. 1991; Karlebach & Shamir 2008)
- Invented vocabulary: why this matters (retrieval confound elimination)
- Phenotype readouts: non-linear summaries, not raw gene states

#### 3.2 Complexity tiers
- Easy / medium / hard (prokaryote / simple_eukaryote / complex_eukaryote)
- Four axes: observability, FFL density, feedback density, latent genes
- Fraction-based scaling so complexity is consistent across organism sizes

#### 3.3 Task structure
- Predict: held-out cross-module double-gene interventions
  - Non-triviality guarantee: ≥0.1 phenotype shift from baseline
- Diagnose (disease mode): malfunction identification — scoring rubric
  - Ambiguity: n_diagnosis_alternatives as a difficulty axis
- Rescue (disease mode): restore phenotypes to healthy range
- Hypothesis: free-text causal summary (qualitative review)

#### 3.4 Benchmark validity
- Detectability guarantee: every disease organism has aberrant phenotypes + rescuable malfunction
- Diagnosis uniqueness: n_diagnosis_alternatives distribution across tiers
- Prediction task non-triviality: empirical shift distribution

#### 3.5 Canonical benchmark
- 20 seeds × medium difficulty × healthy + disease
- Reproducibility: serialization, seed stability, generation versioning

### 4. Experiments (Part 1 — essential)
#### 4.1 Models evaluated
- Heuristic baseline (BLOCK each gene, additive prediction)
- GPT-4o, GPT-4.1, GPT-5.1
- Claude Opus 4.6, Claude Sonnet 4.6

#### 4.2 Metrics
- Prediction: MSE + accuracy (fraction within ±0.15)
- Composite score
- Diagnosis: exact/partial/wrong (1.0/0.5/0.0)
- Rescue: fraction of aberrant phenotypes restored
- Budget efficiency: fraction of budget used

#### 4.3 Results — healthy mode (20 seeds, medium)
- Models vs heuristic baseline
- Does complexity tier matter? (easy → medium → hard)
- Budget usage patterns: does the model exhaust budget or stop early?

#### 4.4 Results — disease mode (20 seeds, medium)
- Diagnosis accuracy: do models find the right gene AND the right type?
- Rescue effectiveness: does diagnosis accuracy predict rescue success?
- Ambiguous organisms: diagnosis accuracy vs n_diagnosis_alternatives

#### 4.5 The complexity threshold
- At what difficulty tier do current models fail?
- Key question: does performance degrade gracefully or cliff?
- Hard tier with latent genes: does budget exhaustion correlate with failure?

### 5. Analysis
- Strategy analysis: do models run targeted experiments or exhaustive sweeps?
- Causal hypothesis quality: spot-check submitted hypotheses
- Failure modes: budget exhaustion, wrong diagnosis type, baseline prediction

### 6. Conclusion (Part 1)
- LEMONOIDS isolates causal reasoning from retrieval
- Current frontier models (GPT-5.1, Claude Opus) can solve medium difficulty
- Hard difficulty with latent genes and feedback loops remains largely unsolved
- Open release, extensible design

---

## Part 2 — Large-scale experiments (positioning TBD)
*Depends on Part 1 results. Could extend Part 1 into a main track paper, or be a separate follow-up.*

### Candidate directions (choose based on what Part 1 reveals)

**A. Probing causal representations**
- Probe questions after session: "which gene most strongly drives phenotype X?" scored vs ground truth
- Separates *knowing the network* from *succeeding at the task*
- Requires structured hypothesis format or LLM-as-judge

**B. Transfer: healthy → disease**
- Run agent on healthy organism, then immediately on the disease version of the same organism
- Does prior knowledge accelerate diagnosis? Measure: diagnosis accuracy, budget used
- Tests whether models build reusable causal models or start fresh each session

**C. Knowledge vs. brute force**
- Hard tier: budget is too small to exhaust all genes
- Do successful agents form genuine causal models, or do they get lucky with greedy search?
- Metric: prediction accuracy on held-out interventions *not* similar to observed ones

**D. Non-LLM baselines**
- Linear regression, random forest, nearest-neighbour in intervention space
- Lower bound: what does pure statistical pattern matching get?
- Upper bound: oracle with full network knowledge

**E. Scaling analysis**
- Does model performance scale with model size / compute?
- Sonnet vs Opus vs o-series on hard organisms
- Relevant if API access allows systematic comparison

---

## Open questions to resolve before writing

1. ~~Do we have Anthropic API access for Claude results?~~ ✅ unblocked
2. What does GPT-5.1 actually do on hard organisms? (need to run)
3. Is the composite score the right primary metric, or should MSE be primary?
4. How do we handle/report organisms where disease generation fails (very rare)?
5. Should n_diagnosis_alternatives be a benchmark split variable?

---

## Timeline (7 weeks to NeurIPS deadline ~2026-05-02)

| Week | Milestone |
|------|-----------|
| 1 | Experiment design finalised; scripts ready; kick off full runs |
| 2–3 | 20-seed canonical runs: all models × healthy + disease × medium |
| 3–4 | Difficulty sweep (easy/medium/hard); ambiguity analysis |
| 4 | Results in hand; Part 1 draft started |
| 5 | Part 1 draft complete; figures done |
| 6 | Internal review + revisions |
| 7 | Submit |
