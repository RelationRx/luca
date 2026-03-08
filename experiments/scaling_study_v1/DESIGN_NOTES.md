# LEMONOIDS — Design Notes & Open Questions

---

## Benchmark Stress-Test (2026-03-04)

### 1. Balance
- **Ceiling effect at small n** — 25/27 perfect diagnosis at n≤20; bottom two-thirds of the difficulty range are not discriminating
- **Scoring too coarse** — 0/0.5/1.0 for diagnosis gives almost no statistical resolution
- **Rescue not earning its place** — 27/27 successful even when diagnosis fails; not differentiating
- **Prediction tasks don't scale** — always 2 tasks regardless of n; gets relatively easier at higher n

### 2. Stability
- **Organism difficulty uncontrolled within n** — malfunction on a hub gene vs. leaf gene is very different difficulty; seed dominates signal (e.g. n=35 seed=1: succeeded at 0.5×, failed at 1.0×)
- **Detectability guarantee ≠ difficulty control** — guarantees solvability, not findability within budget
- **Multiple fixed points unverified** — sigmoid dynamics could converge differently under different initialisations

### 3. Removed from real biology
- **Malfunction type vocabulary is contaminated** — GOF/LOF/chronic_signal are standard genetics; agent can reason from pretraining priors (GOF→KO, LOF→OE) without running experiments
- **Intervention vocabulary contaminated** — KO/OE/KD are molecular biology 101
- **Module concept is biologically familiar** — primes biological reasoning strategies
- **Fix**: replace all biological terminology with abstract equivalents throughout (GOF→"type-A malfunction", KO→"suppress", module→"cluster")

### 4. Complexity
- **Search space grows super-linearly, budget grows linearly** — but it's still bounded exhaustive search at all tested n, not qualitatively different reasoning
- **Systematic sweep works without causal modelling** — try KO on every gene, rank by phenotype impact; doesn't require network reasoning
- **Cross-module interactions underrepresented** — p_intra >> p_inter means most causal chains are local; easier to decompose than real GRNs

### 5. Gaming strategies (critical)

| Strategy | Mechanism | Severity |
|----------|-----------|----------|
| **Rescue oracle exploit** | test_rescue() costs 1 experiment; sweep KO/OE across all genes to identify malfunction without causal reasoning; O(n) experiments | **Critical** |
| **Type-based shortcut** | 3 malfunction types × deterministic rescue = triage strategy; no network reasoning required | **Critical** |
| **Free hypothesis + score feedback** | If multiple submissions allowed, 0/0.5/1.0 score leaks whether type or gene is correct | **High** |
| **Complete empirical mapping** | At small n + generous budget, run all single-gene interventions; answer predictions by lookup table, no generalisation needed | **Medium** |

### 6. Information leaks

| Leak | Description | Severity |
|------|-------------|----------|
| Budget reveals n_genes | budget = n_genes + n_signals + 8; simple arithmetic | Low |
| Aberrant phenotypes at start | Strong hint before any experiments run | Medium |
| 0.5 partial score | Reveals which of {type, gene} is correct | High |
| Observable gene list | If malfunction genes over-represented in observable set | Medium |

### Priority fixes

| Issue | Severity | Fix |
|-------|----------|-----|
| Rescue oracle exploit | Critical | Increase test_rescue cost or blind rescue type |
| Malfunction type vocabulary | Critical | Replace with abstract terms |
| Free hypothesis submission | High | One submission only, no score feedback |
| Difficulty uncontrolled within n | High | Add difficulty stratification metric |
| Ceiling effect at small n | Medium | Start evaluation at n≥25 or reframe small n as calibration |
| Budget coupled to n | Medium | Make budget an independent axis |
| Prediction tasks don't scale | Medium | Scale n_prediction_tasks with n |

---

## Complexity Modulation (beyond n_genes)

Rather than using n_genes as the only complexity axis, modulate via **network structure and dynamics**:

### Proposed difficulty tiers

| Tier | Dynamics | Structure | Observability | Noise |
|------|----------|-----------|---------------|-------|
| **Easy** | Near-linear (small sigmoid steepness) | DAG only, no feedback | All genes observable | ε ~ 0.01 |
| **Medium** | Full non-linear sigmoid | Feedback loops allowed | Some latent genes (20%) | ε ~ 0.05 |
| **Hard** | Full non-linear + bistability | Guaranteed feedback loops, long-range cross-module edges | Multiple latent nodes (30%+) | ε ~ 0.10 |

### Why this matters
- n_genes controls **search space size** (how many variables to consider)
- Structure/dynamics controls **reasoning depth** (how sophisticated the inference needs to be)
- These are orthogonal — creates a 2D complexity space
- Separates agents that are good at *search* vs. agents that are good at *reasoning*
- A systematic sweep agent fails on small-n feedback/latent networks; a deep reasoning agent excels there

### Latent nodes
- Nodes that influence the network but cannot be directly observed or intervened on
- Agent sees their downstream effects but cannot target them
- Requires genuine causal model building to identify
- Maps directly to confounding variables in causal inference literature

### Connection to identifiability theory
- Linear DAG → identifiable from interventional data (easy)
- Non-linear DAG → identifiable under mild assumptions (medium)
- Feedback loops → non-identifiable without additional constraints (hard)
- Latent variables → the classic unidentifiability problem (hardest)

---

## Related Work Notes

### Owkin ZERO (blog post, may become preprint)
- Synthetic GRNs, RL post-training on Qwen3, passive single-turn edge identification
- Different question: "can RL teach causal reasoning?" vs. LEMONOIDS: "how does an agent reason under budget constraints?"
- No active experiment design, no budget, single task
- Cite as parallel motivation, not competitor

### TinyMoves (our preprint, arXiv 2602.09801)
- Move-based hypothesis refinement, game framework
- LEMONOIDS is the benchmark TinyMoves needs; natural connection
- TinyMoves agent as a structured baseline for LEMONOIDS experiments

---

## Open Questions

- [ ] Should LEMONOIDS use abstract vocabulary throughout (no biological terms)?
- [ ] How to control organism difficulty within a given n?
- [ ] Should rescue cost more or be redesigned entirely?
- [ ] How many prediction tasks should scale with n?
- [ ] Is the fixed-point assumption defensible for the benchmark's stated goals?
- [ ] Should we add an explicit "declare unsolvable" action?
- [ ] How to handle latent nodes in the scoring — can agent submit hypothesis about a gene it never observed?
