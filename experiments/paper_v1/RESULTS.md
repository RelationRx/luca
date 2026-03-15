# Paper v1 — Results Summary

Last updated: 2026-03-15. All 4 sweeps complete.

---

## Composite Score (mean ± std)

| Model | Easy (healthy) | Medium (healthy) | Hard (healthy) | Medium (disease) | N ok (E/M/H/D) |
|---|---|---|---|---|---|
| heuristic | 0.717±0.159 | 0.725±0.132 | 0.717±0.176 | 0.553±0.193 | 20/20/20/19 |
| claude-sonnet-4-6 | 1.000±0.000 | 0.983±0.050 | 0.867±0.125 | 0.866±0.166 | 20/20/20/19 |
| claude-opus-4-6 | 1.000±0.000 | 0.983±0.050 | 0.908±0.111 | 0.907±0.134 | 20/20/20/18 |
| gpt-4o | 0.975±0.060 | 0.843±0.090 | 0.833±0.132 | 0.478±0.138 | 20/17/19/18 |
| gpt-4.1 | 0.941±0.098 | 0.833±0.136 | 0.756±0.159 | 0.567±0.215 | 17/18/15/**10** |
| gpt-5.1 | 0.975±0.079 | 0.895±0.135 | 0.794±0.157 | 0.694±0.182 | 20/19/17/**4** |

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

---

## Open Questions / Next Steps

- **gpt-5.1 disease**: only 4 valid seeds — consider a targeted re-run with `max_tokens`
  cap per response to prevent context exhaustion. Would make the disease comparison fairer.
- **Hard organism characterisation**: seeds that consistently fail across model families
  (e.g. hard seeds 3, 8, 10) — characterise topology (feedback density, latent gene fraction).
- **Dataset statistics table**: compute per-tier n_genes, n_phenotypes, n_prediction_tasks,
  n_diagnosis_alternatives distribution from JSONL results for §2.4.
- **Budget utilisation analysis**: do models that use more budget score higher? Claude vs GPT
  budget efficiency on hard organisms.
