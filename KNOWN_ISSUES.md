# Known issues

**Last updated: 2026-11-12. This list is not final — an audit is in
progress.**

A code review in November 2026 found defects in the benchmark engine and in
the analysis scripts that produce the numbers in our write-ups. We are
working through them in the open. This page records what is confirmed, what
is fixed, and what is still open.

An audit of the analysis layer has since added two further issues, and
corrected two earlier entries (10 and 11) that were described inaccurately
here. In both of those cases the correction makes the defect **smaller** than
we first reported.

## If you are using this repository

- **Do not compare models to each other using our published tables.** The
  tool layer silently discarded experiments from some models and not others
  (issue 13). This is the most serious issue on this page.
- **Do not treat the easy or medium tiers as a test of non-additive causal
  reasoning.** Every prediction task at those tiers is solvable by measuring
  each gene separately and adding the effects (issue 2). The hard tier is
  not: about 55% of its tasks resist that strategy.
- **Do not rely on the published baseline numbers.** The heuristic baseline
  computed its own predictions with an inverted sign (issue 6).
- **Treat disease-mode results with particular care.** Signal-level
  malfunctions behave differently from the documentation (issue 5).
- **Check your own agent's calls against the documented format.** If your
  agent does not use the `interventions` key, its experiments may be doing
  nothing (issue 13). A returned result is not proof that an intervention was
  applied.
- **Results generated before these fixes are not comparable to results
  generated after.** Record the commit you ran, not just the seed.

If you are building on this benchmark and want to know whether a specific
issue affects you, open an issue and ask. We would rather answer than have
you discover it later.

## Confirmed issues

| # | Issue | Affects | Status |
|---|---|---|---|
| 1 | `run_experiment` and `test_rescue` would execute a revealed prediction task's exact combination, so an agent could measure the answer instead of predicting it | held-out protocol | **fixed**, not yet in this repo |
| 2 | Every easy and medium prediction task is solvable by a four-experiment additive strategy, contradicting the stated non-additivity guarantee | difficulty claims | open — needs a generator change |
| 3 | `verify_organisms.py` looks up gene IDs in a dictionary keyed by gene names, silently reads every measured effect as zero, and so reports every task as non-additive | organism verification, seed screening | open |
| 4 | `submit_prediction` disclosed ground truth and scored every retry, so a resubmitted answer raised the session average | scoring integrity | **fixed**, not yet in this repo |
| 5 | Signal semantics disagree with the documentation in three ways: a bare `"activate"` resolves to the strength the simulator already uses and does nothing; the documented `{"type": "activate"}` form deactivates instead; an inhibitory `PERSIST` malfunction is negated twice and acts as strong activation | disease mode, signal diagnosis | open |
| 6 | The heuristic baseline subtracted its own measured `BLOCK` delta instead of adding it, and treated `DAMPEN` as the opposite of `BLOCK` | baseline comparisons | **fixed**, not yet in this repo |
| 7 | The `v1-generation-freeze-2` tag named in `DECISIONS.md` predates a package rename and a vocabulary change, and does not reproduce current organisms | reproduction instructions | open |
| 8 | `_composite_score` always divides by three in disease mode, so a run with a task subset is penalised for tasks it was not asked to perform | CLI subset runs only | open |
| 9 | Diagnosis is scored on one irrevocable attempt while rescue takes the best of every attempt | diagnosis-rescue comparisons | open — needs disclosure |
| 10 | **(corrected)** Five analysis scripts model a signal activation as a tenfold override. The live engine applies the signal's ordinary strength, and with the sign taken from the requested action rather than from the signal's mode | discriminating-evidence analysis | open — measured effect smaller than first reported, see below |
| 11 | **(corrected)** The probe item builder uses the same tenfold, mode-signed convention as issue 10 when it constructs items about signal activation | probe studies | open — **no item is mis-keyed**, see below |
| 12 | `run_experiment` never validates an intervention's type. An unrecognised type is silently ignored, costs one unit of budget, and returns no error | agent feedback | open |
| 13 | **The tool layer accepted intervention formats that it then ignored.** A request that did not use the documented `interventions` key reached the engine as an empty experiment: charged one unit of budget, returning the unperturbed organism and no error | **cross-model comparisons** | open — see below |

Issues 1–8 came from the November 2026 review. Issues 9–11 were found while
investigating it. Issues 12 and 13 were found by a subsequent audit of the
analysis layer.

## Issue 13, in detail

This is the one most likely to affect a reader's conclusions.

`run_experiment` reads the `interventions` key, or `gene_interventions`, and
nothing else. Some models sent a flat mapping such as `{"G001": "BLOCK"}`
instead. That reaches the engine as an empty experiment. The engine simulates
the unperturbed organism, charges one unit of budget, and returns a normal
result. No error is raised, so a model has no way to learn that its format was
wrong, and it repeats the format for the whole session.

Measured across 860 stored sessions, as a share of billed experiments that
applied nothing:

| Model | Budget spent on empty experiments | Sessions where every experiment was empty |
|---|---:|---:|
| gpt-4.1 | 46.9% | 44 of 117 |
| gpt-4o | 28.2% | 36 of 121 |
| gpt-5.1 | 8.7% | 8 of 124 |
| claude-opus-4-6 | 0.3% | 0 |
| claude-sonnet-4-6 | 0.0% | 0 |
| qwen-3.5 | 0.3% | 0 |
| deepseek-v3 | 0.2% | 0 |

The models that used the documented format were unaffected. The models that
did not were scored on sessions in which much of their budget bought nothing.

Our published hard-tier ordering does not survive this. Restricted to sessions
whose experiments reached the engine, `gpt-4.1` scores above both Claude models
on both hard sweeps, where our tables place it below them. We are not yet
claiming the corrected ordering is right — those subsets are small, and the
split conditions on a model's own behaviour. We are saying the published
ordering rests on sessions in which one model's experiments were discarded,
and should not be relied on.

## Corrections to issues 10 and 11

We described both more broadly than the evidence supports. Both corrections
reduce the scope.

**Issue 10.** The tenfold override appears at six places in five analysis
scripts, not one. One of those six is **correct**: the generator really does
use a tenfold severity for a persistent-signal malfunction, so the script that
reconstructs that malfunction is right to use it. The incorrect uses are those
that model an agent's own signal activation.

Measured effect: no organism's discriminating set depends on it. Removing
every signal-activation entry leaves the same 92.5% of alternatives
resolvable, and the same 39 of 60 organisms fully resolvable. What does change
is that 6.4% of the evidence-seeking actions we credited to agents were signal
activations that did nothing.

**Issue 11.** We said items involving signal faults "may mark correct
reasoning as wrong". **They do not.** All 16 affected items are *filler*
items — deliberately non-discriminating items used to test whether a model can
recognise non-evidence. A filler's answer key is fixed by its category, never
by its numbers, and a no-op experiment is still non-evidence. No item is
mis-keyed, and none of the 69 discriminating items is affected.

The real flaw is narrower and is about reproducibility: 13 of those 16 items
pair an observation taken from a real session with predictions from a
simulation the engine cannot produce, so a reader recomputing the item would
not obtain the stated numbers.

## Reproducing any of these

The reproduction scripts live in the development repository and will be
mirrored here with the fixes. Each issue above was confirmed by direct
measurement, not by inspection alone.

## What happens next

1. ~~Finish auditing the analysis scripts.~~ A first pass is done; it produced
   issues 12 and 13 and the corrections to 10 and 11. The scaling-study logs
   and several analysis scripts are still unexamined.
2. Land the remaining engine fixes.
3. Recompute every affected number, and re-run the sessions that the
   held-out protocol change invalidates.
4. Post corrected versions of the write-ups, with the corrections stated
   plainly rather than folded into updated tables.
