# LEMONOIDS Part 3 — Knowledge Integration Extension

**Status**: Research note / idea stage. Not included in current paper.
**Prerequisites**: Parts 1 and 2 complete.

---

## Motivation

Parts 1 and 2 establish two things:

1. There is a complexity threshold (some N, some feedback density) above which
   current models fail at causal reasoning in LEMONOIDS.
2. Below that threshold, models differ in *how* they reason — some do systematic
   exploration, some jump to priors, some enumerate exhaustively.

A natural follow-on question: when models hit the complexity wall, can they
fall back on **prior knowledge** to partially compensate? In real science, a
researcher who cannot fully characterise a complex pathway does not start from
scratch — they draw on known organism-class behaviour, published findings, or
domain rules of thumb. The current benchmark, by design, makes all prior
knowledge uninformative. Part 3 would relax this constraint in a controlled way.

The core hypothesis:
> Prior knowledge helps most exactly where pure causal reasoning fails —
> i.e., above the complexity threshold identified in Part 2.

If true, this characterises how LLMs integrate knowledge with evidence, and
whether they can do so selectively depending on task difficulty.

---

## Design

### Key design requirement

Knowledge must be provided in the **synthetic vocabulary** to preserve the
retrieval-free property of the benchmark. Agents cannot be given real biology
knowledge (that would reintroduce the retrieval confound). Instead, synthetic
"prior knowledge" is grounded in the same invented gene/module/signal/phenotype
labels as the organism itself.

### Option A — Organism family datasheets (preferred starting point)

Define **organism families**: groups of seeds that share a structural motif
(e.g., "feedback-dominant organisms in the vortex module class typically show
phenotype suppression when genes in the same module are co-blocked").

Before each session, provide the agent with a synthetic **species datasheet**:
a short document (in invented vocabulary) describing known properties of this
organism family — e.g., which modules are feedback-heavy, which signals are
typically dominant, which gene classes tend to drive disease phenotypes.

Individual seeds are instances of the family with variation, so the datasheet
is informative but not fully determining.

**Controllable parameters:**
- **Knowledge accuracy** (fraction of datasheet facts that are true for this seed)
- **Knowledge completeness** (fraction of organism properties covered)
- **Knowledge specificity** (gene-level facts vs module-level generalisations)

### Option B — Synthetic literature snippets

Provide 3–5 short synthetic "prior observation" snippets describing behaviours
observed in *similar* (not identical) organisms. Some snippets are accurate,
some are noisy or outdated. Forces models to weigh prior knowledge against
experimental evidence and update beliefs when evidence contradicts the prior.

More naturalistic than Option A but harder to control precisely.

### Option C — Cross-session transfer (implicit knowledge)

Run agents on a **sequence** of related organisms in the same context window.
The agent builds up knowledge implicitly from early (simpler) organisms and
applies it to harder later ones. No explicit knowledge injection — tests
whether models naturally accumulate and reuse causal patterns across sessions.

Closest to real scientific practice. Hardest to score cleanly (hard to
separate knowledge transfer from within-context reasoning).

---

## Experimental design

### 2×2 core sweep

| | No knowledge | Knowledge provided |
|---|---|---|
| **Below threshold** (medium, N=20) | Part 1 baseline | New condition |
| **Above threshold** (hard, N≥320) | Part 2 result | New condition |

Primary question: does the knowledge benefit (Δ composite score) increase
with complexity?

### Metrics (additions to existing)

- **Knowledge utilisation**: does the agent cite or reference the datasheet
  in its reasoning / hypothesis text? (qualitative, from session logs)
- **Knowledge override rate**: when experimental evidence contradicts the
  datasheet, does the agent update its belief? (requires cases where
  datasheet is deliberately wrong)
- **Diagnosis source**: when diagnosis is correct, was the correct target
  mentioned in the datasheet? (separates knowledge-guided from
  evidence-guided correct answers)

---

## Open questions

1. **How to generate family datasheets programmatically** — needs a generation
   step that produces synthetic natural-language descriptions from GRN
   structure, in the invented vocabulary. Non-trivial but feasible.

2. **Calibrating knowledge accuracy** — if the datasheet is too accurate,
   the task is trivialised (just read the answer). If too noisy, it's
   indistinguishable from no knowledge. Need a principled accuracy level —
   possibly tied to `n_diagnosis_alternatives` so ambiguous organisms get
   informative datasheets.

3. **Interaction with the invented vocabulary** — datasheets must use the
   same synthetic labels as the organism. This is natural for gene names
   (G001 etc.) but requires care for module-level generalisations (do
   module names carry meaning across seeds in the same family?).

4. **Whether Option A or C is the right starting point** — Option A is
   easier to control and score; Option C is more ecologically valid and
   tests a qualitatively different capability (accumulation vs retrieval).
   Could run both.

---

## Connection to the paper narrative

This extension addresses a gap that reviewers of Parts 1/2 will likely raise:
*"What happens if models had some domain knowledge? Is the benchmark too
divorced from how science actually works?"*

The answer is: Part 3 tests exactly that, and the prediction is that knowledge
helps above the threshold, not below — which would be a strong result about
how models integrate prior knowledge with interventional evidence.

Framing for the paper: knowledge integration as the natural next frontier after
pure causal reasoning is characterised.

---

## Status / next steps

- [ ] Decide between Option A and Option C as starting point
- [ ] Design family taxonomy (how many families, what structural motifs)
- [ ] Prototype datasheet generator for one family
- [ ] Pilot on 5 seeds × 2 conditions (no knowledge / knowledge) to check
      the effect size is detectable before committing to a full sweep
