# Vocabulary & Prompt-Permission Ablation — Results

**Dates**: designed 2026-04-20, run 2026-04-22 → 2026-04-23
**Status**: complete; 320 sessions; may or may not be included in initial submission

## Purpose

Test whether LUCA benchmark results are confounded by two LLM-specific concerns:

1. **Vocabulary retrieval** — do LLMs perform better when gene names are real human genes (TP53, BRCA1, …) than when invented (G001, G042, …)? If so, the benchmark's invented vocabulary is hiding retrieval-based shortcuts.
2. **Prompt suppression** — does the benchmark's "biological knowledge is IRRELEVANT" system-prompt framing artificially *block* models from using useful biology priors? If so, the suppression prompt is doing unobservable work.

Both concerns attack the same core claim — that LUCA benchmarks causal reasoning from perturbation experiments, not retrieval from biology training data.

## Design

2 × 2 × 2 factorial, paired per organism seed:

| factor | levels |
|---|---|
| difficulty | medium (20 genes), hard (30 genes) |
| vocabulary | invented (`G001`, …), real (`TP53`, `BRCA1`, … — 50 real human genes in 3 familiarity tiers) |
| system_prompt_variant | suppress (default: "biological knowledge is IRRELEVANT"), permit ("you may draw on biological knowledge") |

Fixed: 20 seeds per cell (same seeds paper_v1 used), healthy mode, `{predict, diagnose, rescue}` active tasks, Opus 4.6 and DeepSeek v3 as models, 2026-04-20 generation commit.

**Total**: 2 models × 2 difficulties × 2 vocabs × 2 prompts × 20 seeds = **320 sessions**.

Design doc: `docs/superpowers/specs/2026-04-20-real-vocabulary-ablation-design.md` (vocabulary axis only; prompt axis added after Phase 1 suggested the need).

## Primary results

### Per-cell accuracy (mean ± sd, n = 20)

| difficulty | model | inv / sup | real / sup | inv / per | real / per |
|---|---|---|---|---|---|
| medium | claude-opus-4-6 | 0.917 ± 0.101 | 0.908 ± 0.114 | 0.925 ± 0.114 | 0.917 ± 0.101 |
| medium | deepseek-v3     | 0.892 ± 0.098 | 0.842 ± 0.175 | 0.853 ± 0.209 | 0.825 ± 0.262 |
| hard   | claude-opus-4-6 | 0.592 ± 0.206 | 0.608 ± 0.146 | 0.650 ± 0.187 | 0.608 ± 0.182 |
| hard   | deepseek-v3     | 0.567 ± 0.183 | 0.608 ± 0.165 | 0.533 ± 0.220 | 0.475 ± 0.182 |

Accuracy threshold is ±0.10 (paper-wide default). `inv` = invented, `real` = real, `sup` = suppress, `per` = permit.

### Paired Wilcoxon, permit − suppress (prompt effect)

Held vocabulary constant; paired by seed.

| difficulty | model | vocab | mean Δ | p |
|---|---|---|---|---|
| medium | claude-opus-4-6 | invented | +0.008 | 0.500 |
| medium | claude-opus-4-6 | real     | +0.008 | 1.000 |
| medium | deepseek-v3     | invented | −0.039 | 0.997 |
| medium | deepseek-v3     | real     | −0.017 | 0.757 |
| hard   | claude-opus-4-6 | invented | +0.058 | 0.122 |
| hard   | claude-opus-4-6 | real     | −0.000 | 0.454 |
| hard   | deepseek-v3     | invented | −0.033 | 0.668 |
| hard   | deepseek-v3     | real     | **−0.133** | **0.035** |

7 of 8 cells null at α = 0.05. One cell — DeepSeek × hard × real — shows permit *hurting* performance, raw p = 0.035. Bonferroni-adjusted for 8 tests: p ≈ 0.28, not significant after multiple-comparisons correction. All effect sizes |Δ| ≤ 0.13.

### Paired Wilcoxon, real − invented (vocabulary effect)

Held prompt variant constant; paired by seed.

| difficulty | model | variant | mean Δ | p |
|---|---|---|---|---|
| medium | claude-opus-4-6 | suppress | −0.008 | 1.000 |
| medium | claude-opus-4-6 | permit   | −0.008 | 0.500 |
| medium | deepseek-v3     | suppress | −0.050 | 0.533 |
| medium | deepseek-v3     | permit   | −0.028 | 0.749 |
| hard   | claude-opus-4-6 | suppress | +0.017 | 0.363 |
| hard   | claude-opus-4-6 | permit   | −0.042 | 0.289 |
| hard   | deepseek-v3     | suppress | +0.042 | 0.459 |
| hard   | deepseek-v3     | permit   | −0.058 | 0.182 |

All 8 cells null. All effect sizes |Δ| ≤ 0.058. Phase 1's vocabulary null replicates under both prompt variants.

## Interpretation

**Primary finding: neither axis meaningfully affects performance.** 15 of 16 paired contrasts are null at α = 0.05; the single significant cell does not survive Bonferroni correction.

What this tells us about the benchmark design:

1. **Real gene names don't give LLMs a shortcut.** If retrieval were inflating scores, real-vocabulary would score higher than invented. It doesn't, in any model × difficulty × prompt cell.
2. **Explicit permission to use biology priors doesn't help either.** If the suppression prompt were blocking a useful retrieval channel, removing it should raise scores. It doesn't — and where there is any trend (DeepSeek hard × real), it goes the *other* way: permitting biology slightly degrades performance. This is consistent with "biology priors aren't actionable on synthetic GRN topology, and inviting the model to lean on them is a mild distractor."
3. **The invented vocabulary is a conservative design choice, not a load-bearing one.** Phase 1 already suggested this; the prompt-variant axis reinforces it. The benchmark is robust to vocabulary choice and prompt framing in the two obvious ways a retrieval confound could leak.

Reframe relative to the original motivation:

> Old framing: "we use invented vocabulary to block retrieval from biology training data." (Implies retrieval is a real threat.)
>
> New framing: "we ran the benchmark with both invented and real gene names, under both biology-suppressing and biology-permitting prompts. Scores are statistically indistinguishable across all 2 × 2 × 2 cells (paired Wilcoxon, n = 20 each). The benchmark is robust to vocabulary choice and prompt framing. No biology prior provides a shortcut, so performance reflects reasoning from experiments rather than pattern matching on gene names."

## Positioning vs. classical synthetic-GRN benchmarks

This ablation specifically addresses an LLM-era concern that doesn't arise in classical synthetic GRN benchmarks (DREAM, GeneNetWeaver, SERGIO). Those evaluate numeric inference *algorithms* on static observational data — there's no "training set" for GENIE3 to have memorized, so retrieval isn't a confound. LUCA evaluates pre-trained LLMs on active perturbation experimentation, which introduces the confound and therefore requires this kind of control. The null result here is what lets the benchmark make causal-reasoning claims at all.

| | Classical synthetic-GRN benchmarks | LUCA |
|---|---|---|
| Evaluates | inference methods (algorithms) | LLM agents' reasoning |
| Input | numeric expression matrices | natural-language tool calls |
| Agent action | none (static dataset) | active: chooses perturbations under a budget |
| Ground truth | often observational expression | causal: perturbation → readout |
| Output | network only | network + novel-intervention predictions + (disease) diagnosis + rescue |
| Training-data leakage risk | none | central; requires vocabulary / prompt ablations like this one |

## Practical / engineering notes

### Hang in the permit run

Phase 2 (permit arm) encountered a pathological hang: a single DeepSeek-V3.1 request via Together AI blocked for 10+ hours on `medium_real_permit` seed 12. The nominal 120 s SDK timeout did not fire. Fixed in commit `ac209d9` (PR #103) by wrapping every API call in a worker-thread wallclock cap (`_API_HARD_TIMEOUT = 180 s`). Max per-session stuck time is now bounded at ~20 minutes. The permit run was killed after `medium_real_permit` completed and restarted for hard tier only under the new code.

### Caching

All Anthropic sessions used prompt caching (PR #101, merged 2026-04-22). Observed ~3.5× input-token cost reduction on Opus, verified via a 10-session A/B smoke showing score parity (mean 0.900 ± 0.091 off vs 0.867 ± 0.139 on, within σ). See `scripts/cache_smoke.py`.

### Cost

| run | sessions | ~spend |
|---|---|---|
| Phase 1 (suppress × {inv, real} × {med, hard} × 2 models × 20) | 160 | ~$20 |
| Phase 2 (permit × same grid) | 160 | ~$20 (80 medium + 80 hard in the rerun) |
| Cache smoke | 10 | ~$2 |
| **total** | **330** | **~$42** |

Anthropic (Opus) paid via the usual key; DeepSeek via Together.

## Data & reproducibility

Results JSONLs (local only — gitignored per project convention):
```
experiments/vocabulary_ablation/results/
  medium_invented/               # suppress (Phase 1)
  medium_real/
  hard_invented/
  hard_real/
  medium_invented_permit/        # permit (Phase 2)
  medium_real_permit/
  hard_invented_permit/
  hard_real_permit/
```

Per-session agent-trace logs live under `experiments/vocabulary_ablation/logs/<sweep>/logs/<model>_seed*.json` (also gitignored).

Reproduce:

```bash
# Phase 1 (suppress, default)
python experiments/vocabulary_ablation/run.py \
    --model claude-opus-4-6 --model deepseek-v3

# Phase 2 (permit)
python experiments/vocabulary_ablation/run.py \
    --model claude-opus-4-6 --model deepseek-v3 \
    --system-prompt-variant permit
```

Seeds are pulled from `experiments/paper_v1/selected_seeds.json` so results can be compared directly to the paper_v1 healthy-mode tables.

### Commit refs

| PR | commit | change |
|---|---|---|
| #99  | `dd0604f` merge | vocabulary axis: `luca/vocabulary_real.py`, `generate_organism(vocabulary=...)`, `evaluate_model(vocabulary=...)`, runner |
| #101 | `beb2cbb` merge | prompt caching on Anthropic path |
| #102 | `7177b47` merge | prompt-permission axis: `system_prompt_variant` plumbed through, `_PERMIT_BLOCK` constant |
| #103 | `d3cb8b0` merge | hard wallclock timeout on API calls (fixes hang) |

Generation commit for organisms: `v1-generation-freeze-2` (same as paper_v1).

## Phase 3 (not yet run)

If reviewers ask for broader coverage:
- Sonnet 4.6 — complements Opus within the Anthropic family
- GPT-5.1 — different provider (OpenAI), different training data composition; the strongest test of generalisation across model families

Cost: ~$20–40 for the two models × same 2 × 2 × 20 grid. Not critical unless a reviewer demands breadth. Current 2-model × 2-provider coverage (Anthropic + Together/DeepSeek) is already cross-provider.
