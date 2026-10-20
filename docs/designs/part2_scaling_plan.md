# Part 2 — Scaling Study Plan

**Last updated:** 2026-03-22

---

## Motivation

Part 1 established that LLM agents (Claude and GPT families) outperform heuristic baselines
on fixed-size organisms (N≈15 genes, medium difficulty). Part 2 asks: **does this hold as
networks grow?** If agents are genuinely building causal models rather than pattern-matching,
their performance should scale more gracefully than a heuristic that can't represent nonlinear
interactions. Including two model families (Claude Sonnet, GPT-4o) lets us test whether
scaling behaviour is a property of capable LLMs generally.

---

## Research Questions

### RQ1 — Does LLM reasoning scale with network complexity?
Do LLM agents maintain high prediction accuracy as N grows from 20 to 1280 genes? We test
two model families (Claude Sonnet, GPT-4o) against a heuristic baseline that uses an
additive approximation — a strategy that breaks on larger nonlinear networks. If agents are
doing genuine causal reasoning, performance should hold up or improve at scale while the
heuristic degrades.

**Expected finding:** LLM agents maintain high accuracy (≥0.85) across all N; heuristic
stays near-chance at ±0.10; gap between LLMs and heuristic widens with N. Claude and GPT-4o
may show different scaling profiles, providing a cross-family comparison.

### RQ2 — Where and why does the heuristic fail?
Preliminary data shows the heuristic near-chance (0.48–0.67) at ±0.10 across all N, and
*random beats heuristic at every N*. This is a strong result: the additive prediction
strategy actively fails, not just plateaus. Part 2 pins down the crossover and explains it
structurally (nonlinear readout dynamics, multi-gene interactions in prediction tasks).

**Expected finding:** heuristic failure is not N-dependent — it fails at N=20 too. The
issue is the prediction task design (cross-module double-gene interventions hit sigmoid
nonlinearities), not organism size per se.

### RQ3 — Does the agent's strategy change with N?
Post-hoc analysis of session logs. Three metrics:

1. **Budget allocation timing**: at what fraction of budget does the agent call
   `get_next_prediction_task()`? Does it allocate more discovery time at large N?
2. **Intervention type mix**: BLOCK/BOOST/DAMPEN proportions by N. Does the agent
   become more targeted (more BOOST/DAMPEN, less BLOCK) as N grows?
3. **Experiment redundancy**: fraction of experiments that re-perturb a gene already
   seen in the session. Does selectivity increase with N (agent learns to prune the
   search space)?

**Expected finding:** agents become more selective at large N — earlier prediction
commitment would be surprising; more redundancy would suggest a less coherent strategy.
Cross-model comparison (Sonnet vs GPT-4o) may reveal whether strategy differences explain
performance differences.

---

## Experiment Layout

### Models
| Model | Role | Notes |
|-------|------|-------|
| claude-sonnet-4-6 | Primary LLM agent | Full sweep, all N |
| gpt-4o | Cross-family comparison | All N including 1280 (exploratory); fail-fast at 80% |
| heuristic | Structured baseline | Full sweep |
| random | Chance baseline | Full sweep |

GPT-4o is included to make RQ1 a claim about capable LLMs generally, not just Sonnet.
GPT-4.1 and GPT-5.1 are excluded: GPT-4.1 is redundant given GPT-4o; GPT-5.1 has
a known context exhaustion failure in disease mode at N≈15 and is likely to fail at
large healthy N too.

GPT-4o runs at all N including N=1280 (treated as exploratory). A **fail-fast** mechanism
skips a model at all larger N values if it fails ≥80% of sessions at a given N
(failure = null score or budget_used=0). This prevents wasting cost if context exhaustion
kicks in at scale, while still allowing moderate failure rates through.

Opus is excluded from the main sweep. Its stall at N≥640 (budget_used=0) is noted as
a one-paragraph observation in the paper: "Opus's pre-tool reasoning scales superlinearly
with N; at N≥640 it exhausts the 16384-token output limit before its first tool call."

**Model budget (10 seeds each):**
- Sonnet (all N): ~$490
- GPT-4o (all N, if no fail-fast): ~$270
- Heuristic + random: free
- **Total estimate: ~$760** (lower bound; large-N sessions may cost 2–3× more due to
  context accumulation; fail-fast may reduce GPT-4o cost if it degrades at large N)

### Design
| Parameter | Value |
|-----------|-------|
| N values | 20, 40, 80, 160, 320, 640, 1280 |
| Difficulty | medium (fixed) |
| Mode | healthy (fixed) |
| Seeds | 0–9 (10 per N, consistent with Part 1 medium healthy) |
| Tasks | predict only (`active_tasks={"predict"}`) |
| Budget | N + N_signals + 8 (formula from `recommended_budget`) |
| Max turns | 50 + N//4 (scales with N, already in `run.py`) |

**Total API sessions:** ~130 (70 Sonnet + 60 GPT-4o; heuristic/random are local, no API cost)

### Estimated cost / time
| N | Approx time per seed (Sonnet) | 10 seeds |
|---|-------------------------------|----------|
| 20–160 | ~2 min | ~20 min |
| 320 | ~5 min | ~50 min |
| 640 | ~10 min | ~100 min |
| 1280 | ~20 min | ~200 min |

Total wall time with parallel model execution: ~6–7 hours (models run in parallel,
seeds sequential within each model).

---

## Implementation Plan

### Step 1 — Update config (`experiments/scaling_v1/config.py`)
- Set `SEEDS = list(range(10))` for all N (currently 5 for N≥320)
- Set `CORE_MODELS = ["claude-sonnet-4-6", "heuristic", "random"]` for all N
- Remove `EXTENDED_MODELS` / `GPT_MODELS` tiers (not used in this sweep)

### Step 2 — Clear old preliminary results
Delete `experiments/scaling_v1/results/` contents (invalidated by RNG fix in PR #44).
Old results were exploratory; Part 2 run is the definitive one.

### Step 3 — Run the sweep
```bash
export $(cat .env | xargs)
python experiments/scaling_v1/run.py
```
Run all N values and all models in one go. Models run in parallel within each N sweep.

### Step 4 — Write strategy analysis script
New script: `experiments/scaling_v1/analyse_strategy.py`

Inputs: session log JSONs from `experiments/scaling_v1/logs/`

Outputs per N × model:
- `prediction_commitment_fraction`: mean experiment index of first
  `get_next_prediction_task` call / total budget
- `intervention_type_mix`: {BLOCK, BOOST, DAMPEN} fractions
- `redundancy_fraction`: re-perturbed genes / total experiments

### Step 5 — Plot results
New script: `experiments/scaling_v1/fig_scaling.py`

Figures:
1. **Main scaling curve**: composite score vs N (Sonnet, heuristic, random). Log x-axis.
2. **Strategy panel**: three subplots (commitment timing, intervention mix, redundancy) vs N.
3. *Optional*: heuristic failure decomposition (prediction error by phenotype type).

### Step 6 — Update paper
- Fill in the Part 2 placeholder in the paper
- Add scaling figure
- Record the final results

---

## Success Criteria

- [ ] Full scaling curve for Sonnet across N=20–1280 (10 seeds each)
- [ ] RQ1 confirmed: Sonnet gap over heuristic widens with N (or characterised if not)
- [ ] RQ2 confirmed: heuristic failure explained structurally
- [ ] RQ3: strategy metrics computed and showing interpretable trends
- [ ] Paper section written and figures generated

---

## Notes

**Why not Opus?** Opus stalls at N≥640 (budget_used=0, all scores null). This is logged
as a finding in session traces (`"stall": true`) but is not the focus of Part 2. Can be
reported as a one-paragraph observation: "Opus's pre-tool reasoning scales superlinearly
with N; at N≥640 it exhausts the 16384-token output limit before issuing its first tool
call."

**Why medium difficulty only?** Part 1 already covers difficulty scaling (easy/medium/hard)
at fixed N. Part 2 varies N — adding difficulty tiers would triple the session count and
muddy the story. Medium is the right fixed point: it's informative (not saturated like easy)
and representative. The two parts are designed as orthogonal axes: Part 1 = difficulty × mode
at fixed N; Part 2 = N at fixed difficulty and mode.

A potential future extension: run a single hard-difficulty point at N=20 and N=80 to ask
"is hard at N=80 equivalent to medium at N=320?" — connecting the two studies. This is
deferred to a supplementary analysis if time allows.

**Why healthy mode only?** Disease mode at large N would be interesting (identifying a single
faulty gene among 640 candidates is genuinely harder), but GPT models already fail at disease
mode at N≈15 in Part 1 due to context exhaustion. At N=320+ they would fail consistently,
making the comparison meaningful only for Claude. Adding disease mode would either require
dropping GPT models (reducing the cross-family story) or reporting a highly incomplete table.
Healthy mode keeps the comparison clean across all model families.

**RNG fix note:** PR #44 fixed non-deterministic experiment noise (shared session RNG
replaced with per-experiment `[seed, budget_used]` RNG). All preliminary scaling_v1
results were generated before this fix and are invalidated. Part 2 is the first clean run.
