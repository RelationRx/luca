# LUCA — Claude Code Context

Synthetic organism reasoning benchmark for LLM agents.
Repo: https://github.com/RelationRx/rrx-luca

## What this project is

GRN (gene regulatory network) organisms with **invented vocabulary** (no real biology terms).
Agents run perturbation experiments under a budget to characterise the organism, predict
cross-module intervention outcomes, and (in disease mode) identify and rescue a malfunction.
The core claim: this benchmarks *causal reasoning*, not retrieval from biology training data.

## Key files

| File | Purpose |
|------|---------|
| `luca/generation.py` | Organism generation; `DIFFICULTY_PRESETS` (easy/medium/hard + aliases) |
| `luca/experiment.py` | `ExperimentSession` — budget-limited perturbation interface |
| `luca/agent.py` | `run_agent()` — routes claude-* → Anthropic, gpt-*/o* → OpenAI |
| `luca/vocabulary.py` | All invented labels (modules, signals, phenotypes, cell types) |
| `evaluate.py` | Benchmark runner; flags: `--model`, `--difficulty`, `--disease`, `--n`, `--seeds` |
| `experiments/paper_v1/run.py` | Paper v1 sweep runner (7 models × 4 sweeps × 20 seeds) |
| `experiments/paper_v1/LAB_JOURNAL.md` | Running log of results, decisions, observations |
| `docs/paper_outline.md` | Paper structure and open questions |
| `DECISIONS.md` | Why key design choices were made |

## Design invariants

- All vocabulary is invented — never use real gene/protein names
- Intervention types: `BLOCK` / `BOOST` / `DAMPEN`
- Malfunction types: `LOCK_HI` / `LOCK_LO` / `PERSIST`
- `submit_malfunction_hypothesis()` must be called before `test_rescue()`; hypothesis is locked on first call; score withheld until `get_summary()`
- Difficulty tiers: easy / medium / hard (aliases: prokaryote / simple_eukaryote / complex_eukaryote)
- Generation is deterministic per seed — use `sorted()` not `list(set())` anywhere ordering matters

## Scoring

**Composite score** (healthy mode) = prediction accuracy (fraction within ±0.10 of true value)

**Composite score** (disease mode) = mean(pred_acc, diagnosis_score, rescue_fraction)
- `diagnosis_score`: 1.0 exact (gene + type), 0.5 partial (gene only), 0.0 wrong
- `rescue_fraction`: fraction of aberrant phenotypes restored to healthy range

**Heuristic baseline**: systematically BLOCKs each gene, uses additive prediction. Budget = 21.
**Random baseline**: predicts 0.5 everywhere, runs no experiments. Budget = 0.

## Benchmark configuration (paper v1)

- 4 sweeps: `B_easy_healthy`, `A_medium_healthy`, `B_hard_healthy`, `A_medium_disease`
- 7 models: claude-opus-4-6, claude-sonnet-4-6, gpt-5.1, gpt-4o, gpt-4.1, heuristic, random
- 20 seeds each → 560 sessions total
- Generation frozen at tag `v1-generation-freeze-2` (commit `57f7be7`)

## Workflow rules

- **Always use a feature branch** — never commit directly to main (`fix/foo` or `improve/foo`)
- **Always open a PR** — main is branch-protected; changes go through PRs
- **Never commit `.jsonl` result files** — results stay local only; `*.jsonl` is gitignored
- **Commit only scripts and `.md` conclusions** — not raw output data
- API keys in `.env` (gitignored); load with `export $(cat .env | xargs)`
- `gh` CLI authenticated as `gogleva` (gogleva.a.a@gmail.com)

## Current status (2026-03-20)

**Part 1 benchmark**: 840/840 sessions complete (7 models × 6 sweeps × 20 seeds).
All scores at ±0.10 threshold. Results in `experiments/paper_v1/results/` (local, gitignored).
See `LAB_JOURNAL.md §10–12` for full results tables. Paper draft: `docs/paper_outline.md`.

**Part 2 scaling study**: N=20–1280 at medium difficulty.
Sonnet scales to 1.000 at N=1280. Opus stalls (budget_used=0) at N≥640 — large-N planning bug, not yet fixed.
Results in `experiments/scaling_v1/results/`. Session logs at `experiments/scaling_v1/logs/` (gitignored).
See `LAB_JOURNAL.md §13` for scaling table and Opus stall analysis.

**Open issues before publishing scaling results**:
1. Opus large-N stall: generates >16384 tokens of planning text before first tool call at N≥640.
   Fix: stall detection + nudge in `agent.py`, or system prompt instructing immediate action.
2. Simulation noise at large N: `simulate_sigmoid` uses shared session RNG → same intervention
   gives different values depending on prior session state. See LAB_JOURNAL.md Open Questions.

**Deadline**: NeurIPS 2026 ~2026-05-02.
