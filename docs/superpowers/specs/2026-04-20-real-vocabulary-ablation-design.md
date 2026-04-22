# Real-Vocabulary Ablation

**Date**: 2026-04-20
**Status**: Approved
**Goal**: Test whether replacing invented gene names (G001) with real biology gene names (TP53, BRCA1) affects LLM prediction performance.

## Motivation

The benchmark uses invented vocabulary to prevent retrieval from biology training data. A reviewer will ask: "How do you know the invented vocabulary isn't imposing a working-memory tax rather than isolating causal reasoning?" This ablation answers that question by running the same organisms with real gene names and comparing scores.

## Design

### What changes

1. **New file `luca/vocabulary_real.py`**: a pool of 50 real human gene names in three tiers:
   - Tier 1 (textbook, 18 genes): TP53, BRCA1, EGFR, MYC, KRAS, RB1, AKT1, PTEN, BRAF, PIK3CA, VEGFA, TNF, IL6, NOTCH1, WNT1, SHH, MAPK1, JAK2
   - Tier 2 (well-known, 16 genes): FOXP3, SOX2, STAT3, SMAD4, CDH1, CTNNB1, FGFR2, ERBB2, HDAC1, SIRT1, MTOR, GSK3B, TGFB1, RAF1, MEK1, DICER1
   - Tier 3 (niche, 16 genes): LMNA, PPARG, CEBPA, KDM5A, SETD2, ARID1A, STAG2, KMT2D, FBXW7, NSD1, BCOR, CREBBP, EP300, PHF6, CUX1, ASXL1

2. **New parameter on `generate_organism()`**: `vocabulary="invented"` (default) or `vocabulary="real"`. When `"real"`, gene names are drawn from the real pool instead of G001-G020, shuffled per seed via the organism RNG so the mapping is random and different for each organism.

3. **System prompt unchanged**: still warns about invented vocabulary. This is intentional — we're testing whether LLMs can ignore priors when told to. If the system prompt said "these are real genes", the ablation would test a different question.

### What does NOT change

- GRN topology (same edges, same dynamics, same seeds)
- Phenotype labels (stay invented: energy-state, etc.)
- Signal labels (stay invented)
- Module labels (stay hidden)
- Scoring, budget, prediction tasks
- Everything except the gene name strings

### Key design choice: random mapping per seed

Gene names are shuffled per seed so that TP53 maps to a different GRN position in each organism. This prevents cross-seed learning ("TP53 is always a hub") and ensures the ablation measures name-level retrieval, not positional correlation.

## Experiment plan

### Phase 1 (initial, Opus + DeepSeek)

- Medium healthy: 20 seeds × 2 models × 2 vocabulary = 80 sessions
- Hard healthy: 20 seeds × 2 models × 2 vocabulary = 80 sessions
- Total: 160 sessions
- Cost: ~$40 (Opus ~$35, DeepSeek ~$5)

### Phase 2 (expand if results warrant, time permits)

- Add remaining LLMs (Sonnet, Qwen, GPT-5.1, GPT-4o, GPT-4.1)
- Add disease mode
- Run CausalSweep + heuristic as controls (should be unaffected — they don't read names)

### Analysis

Paired comparison per seed: same organism topology, same model, invented vs real names. Wilcoxon signed-rank test per model per tier (N=20 paired observations). Report:
- Mean score difference (real - invented) with 95% CI
- Per-seed scatter plot (invented score vs real score)
- Qualitative: do agents mention gene function in their hypotheses when given real names?

### Expected outcomes

- **Real ≈ invented**: vocabulary doesn't matter. The invented vocabulary control is conservative but unnecessary. LLMs reason from experiments regardless of names.
- **Real < invented**: prior knowledge interferes. LLMs can't ignore what they "know" about TP53. Confirms the invented vocabulary is actively necessary.
- **Real > invented**: structural priors transfer. Weakens the "pure reasoning" claim. Would need careful discussion.

## Output for the paper

One table (2 models × 2 tiers × 2 conditions = 8 cells) and one paragraph in the main text or supplementary. Either confirms the vocabulary design choice or reveals an interesting confound.

## Implementation scope

- `luca/vocabulary_real.py` — new file, ~50 gene names
- `luca/generation.py` — add `vocabulary` parameter, swap gene name pool when `"real"`
- `experiments/vocabulary_ablation/run.py` — small runner script
- Test: verify same seed with both vocabularies produces identical GRN topology (only names differ)
