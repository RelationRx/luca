# LEMONOIDS — Paper Outline

**Target venue:** NeurIPS 2026 (Datasets & Benchmarks track)
**Deadline:** ~2026-05-02 (7 weeks from 2026-03-14)
**Working title:** *LEMONOIDS: A Synthetic Organism Reasoning Benchmark for LLM Agents*

---

## Status (2026-03-19)

**Part 1 complete.** 840/840 sessions across 6 sweeps (easy/medium/hard × healthy/disease),
7 models × 20 seeds each. Paper sections filled in (`lemonoids-paper/main.tex`).
Remaining TODOs: introduction narrative, related work, appendices, figures, author list.

**Part 2 planning:** network scaling study (N=20→40→80→160). Design to be finalised 2026-03-19.

---

## Framing

The core claim: current LLM benchmarks conflate *retrieval* with *reasoning*. A model that has
memorised biology textbooks will score well on biology tasks — but does it actually reason causally?
LEMONOIDS removes retrieval entirely (invented vocabulary, no real gene names) and forces models to
build causal models from perturbation experiments under budget constraints. It is a benchmark for
*causal reasoning under uncertainty*, not knowledge recall.

---

## Part 1 — Benchmark design + essential experiments
*Status: experiments complete, paper draft in progress.*

### 1. Introduction
- LLMs increasingly deployed as reasoning agents in science
- Existing benchmarks: knowledge retrieval, math, code — not causal reasoning from data
- The retrieval confound: models with biological priors can "cheat" on biology benchmarks
- LEMONOIDS: a benchmark that is *unknowable via retrieval* by construction
- Contributions: benchmark design, complexity tiers, disease mode, baseline results across 840 sessions

### 2. Related work
- Scientific reasoning benchmarks (GPQA, SciEval, LAB-Bench, etc.)
- Agent benchmarks with tool use (SWE-bench, WebArena, etc.)
- Causal reasoning benchmarks (CausalBench, etc.)
- Perturbation-based biology (CRISPR screens, drug response) — motivation, not prior work
- Key gap: no benchmark isolates causal reasoning from retrieval in a controlled, scalable way

### 3. Benchmark design (written)
- Organism model: sigmoid GRN dynamics, invented vocabulary
- Complexity tiers: easy / medium / hard across 4 axes (observability, FFL density, feedback density, latent genes)
- Task structure: predict + diagnose + rescue
- Generation validity guarantees (full coverage, non-additive tasks, latent gene relevance, baseline centering)
- Reproducibility: deterministic generation, generation freeze tag `v1-generation-freeze-2`

### 4. Experiments (written)
- 7 models: claude-opus-4-6, claude-sonnet-4-6, gpt-5.1, gpt-4o, gpt-4.1, heuristic, random
- 6 sweeps: easy/medium/hard × healthy/disease; 20 seeds each; 840 sessions total

#### Key results (Part 1)

**Composite score (mean ± std)**

| Model | Easy H | Med H | Hard H | Easy D | Med D | Hard D |
|---|---|---|---|---|---|---|
| claude-opus-4-6 | 1.000 | 0.967 | 0.792 | 0.944 | 0.833 | 0.714 |
| claude-sonnet-4-6 | 0.983 | 0.917 | 0.725 | 0.822 | 0.769 | 0.650 |
| gpt-5.1 | 0.942 | 0.850 | 0.717 | 0.353 | 0.317 | 0.192 |
| gpt-4o | 0.917 | 0.783 | 0.650 | 0.558 | 0.456 | 0.431 |
| gpt-4.1 | 0.900 | 0.767 | 0.592 | 0.489 | 0.378 | 0.456 |
| heuristic | 0.775 | 0.733 | 0.342 | 0.531 | 0.611 | 0.475 |
| random | 0.800 | 0.750 | 0.483 | 0.475 | 0.492 | 0.350 |

**Diagnosis score (disease mode)**

| Model | Easy D | Med D | Hard D |
|---|---|---|---|
| claude-opus-4-6 | 0.850 | 0.600 | 0.400 |
| claude-sonnet-4-6 | 0.500 | 0.450 | 0.350 |
| gpt-5.1 | 0.100 | 0.050 | 0.000 |
| gpt-4o | 0.125 | 0.050 | 0.100 |
| gpt-4.1 | 0.100 | 0.050 | 0.200 |
| heuristic | 0.100 | 0.350 | 0.300 |
| random | 0.000 | 0.050 | 0.025 |

#### Key findings
1. Easy healthy is saturated (all LLMs 0.90–1.00)
2. Disease mode is the separator — healthy/disease gap is small for Claude (~0.05–0.08 on composite), catastrophic for GPTs on hard disease (gpt-5.1: 0.717 → 0.192)
3. Diagnosis is the crux — GPTs stuck at ~0.05 regardless of tier; Claude degrades gracefully
4. Heuristic beats all GPTs on medium/hard disease diagnosis — exhaustive enumeration outperforms LLM abduction
5. No model correctly diagnosed a signal-level malfunction (gene attribution bias)
6. Rescue ≠ root-cause diagnosis — models can restore phenotypes without identifying the true malfunction
7. gpt-5.1 paradox — best GPT on healthy, collapses on disease (context exhaustion + batching)
8. Hard organisms: heuristic collapses *below* random (0.342 vs 0.483) — feedback makes additive prediction harmful

### 5. Analysis (written in paper)
- Experimental strategy (Claude: systematic BLOCK sweep, full coverage; GPTs: 2–3% gene coverage)
- Budget utilisation (Claude 75–88% consistent; GPTs variable and low)
- Failure modes: GPT context exhaustion, gpt-4.1 zero-experiment strategy, gene attribution bias, ambiguity threshold
- Rescue ≠ diagnosis case study (seed 0, thermal-pulse PERSIST)

### 6. Conclusion (written)
Three headline findings: heuristic beats GPTs on diagnosis, rescue ≠ diagnosis, gene attribution bias.

---

## Part 2 — Network scaling study
*Status: design phase. Planning session 2026-03-19.*

### Core hypothesis
At N=20, prediction is tractable for all frontier models (budget covers a full BLOCK sweep).
Scaling to N=40/80/160 makes prediction hard too — budget insufficient for full sweeps, forcing
genuine prioritisation. Expected: three regimes (ceiling / discriminative / collapse), analogous
to the "Illusion of Thinking" pattern observed in extended thinking models.

### Design sketch

**Network sizes:** N=20, 40, 80, 160 (budget scales as N + N_signals + 8)

| N | Budget | Observable genes | Signals |
|---|---|---|---|
| 20 | 31 | 12 (medium) | 3 |
| 40 | 54 | ~24 | ~6 |
| 80 | 99 | ~48 | ~11 |
| 160 | 191 | ~96 | ~23 |

**Models:** claude-sonnet-4-6, heuristic, random as core sweep.
claude-opus-4-6 + gpt-4o at N=80/160 for cross-family comparison at scale.

**Difficulty:** medium only (isolate network size from tier complexity)

**Mode:** healthy only (disease mode at large N would worsen GPT context exhaustion further)

**Seeds:** 5–10 per N value (fewer needed — variance from N dominates)

### Questions to resolve in planning session
- How many seeds per N? (5 or 10)
- Which models at which sizes? (cost/API constraint)
- Should we run disease at N=40 to extend the disease story?
- Metrics: budget utilisation fraction expected to drop as N grows — measure this
- Do we need a new `select_seeds.py` run for larger organisms?

### Candidate additional directions (post-scaling)
- **Transfer: healthy → disease** — run agent on healthy first, then disease of same organism. Does prior knowledge accelerate diagnosis?
- **Probing causal representations** — post-session probe questions scored vs ground truth network
- **Non-LLM statistical baselines** — linear regression, random forest on intervention data

---

## Paper TODO list

### Writing (remaining)
- [ ] §1 Introduction — narrative, positioning, contributions list
- [ ] §6 Related work — fill in citations (GPQA, SciEval, LAB-Bench, SWE-bench, CausalBench)
- [ ] Appendices: generation algorithm details, agent prompts, extended results tables
- [ ] Broader impact statement
- [ ] Author list

### Figures needed
- [ ] Fig 1: composite score vs difficulty tier (line plot, one line per model, 3 healthy tiers)
- [ ] Fig 2: disease sub-score breakdown (grouped bar: pred/diag/rescue per model, medium disease)
- [ ] Fig 3: difficulty × mode heatmap (6-cell grid, composite score)
- [ ] Fig 4 (Part 2): composite vs N_genes (scaling curve, 3 models)
- [ ] Optional: budget utilisation vs accuracy scatter; diagnosis by n_alternatives bar chart

### Infrastructure
- [ ] Update `analyse.py` SWEEPS to include C_easy_disease and C_hard_disease
- [ ] Figure plotting scripts in `experiments/paper_v1/`
- [ ] Part 2 sweep runner and config

---

## Timeline

| Week | Date | Milestone | Status |
|---|---|---|---|
| 1 | Mar 14 | Experiment design, scripts, kick off runs | ✅ Done |
| 2 | Mar 21 | Part 1 results complete; paper draft started | ✅ Done (early) |
| 3 | Mar 28 | Figures done; Part 2 design finalised; scaling runs kicked off | ← **here** |
| 4 | Apr 4 | Part 2 results in hand; §4–5 expanded with scaling story |  |
| 5 | Apr 11 | Full draft complete; internal review |  |
| 6 | Apr 18 | Revisions; related work polished; appendices done |  |
| 7 | Apr 25 | Final checks; submit by May 2 |  |
