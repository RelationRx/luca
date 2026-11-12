# Known issues

**Last updated: 2026-11-12. This list is not final — an audit is in progress.**

A code review in November 2026 found defects in the benchmark engine and in
the analysis scripts that produce the numbers in our write-ups. We are
working through them in the open. This page records what is confirmed, what
is fixed, and what is still open.

## If you are using this repository

- **Do not treat the easy or medium tiers as a test of non-additive causal
  reasoning.** Every prediction task at those tiers is solvable by measuring
  each gene separately and adding the effects (issue 2). The hard tier is
  not: about 55% of its tasks resist that strategy.
- **Do not rely on the published baseline numbers.** The heuristic baseline
  computed its own predictions with an inverted sign (issue 6).
- **Treat disease-mode results with particular care.** Signal-level
  malfunctions behave differently from the documentation (issue 5).
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
| 10 | `discrimination_analysis.py` models signal activation as a tenfold override, which is not what the live engine does, so agents may be credited with evidence they never received | discriminating-evidence analysis | open |
| 11 | The probe item builders compute their oracle answers with the same signal sign convention as issue 5, so items involving signal faults may mark correct reasoning as wrong | probe studies | open |

Issues 1–8 came from the November 2026 review. Issues 9–11 were found while
investigating it, in the analysis layer rather than the engine.

## Reproducing any of these

The reproduction scripts live in the development repository and will be
mirrored here with the fixes. Each issue above was confirmed by direct
measurement, not by inspection alone.

## What happens next

1. Finish auditing the analysis scripts. The engine has been reviewed twice;
   the scripts that turn sessions into published numbers have not.
2. Land the remaining engine fixes.
3. Recompute every affected number, and re-run the sessions that the
   held-out protocol change invalidates.
4. Post corrected versions of the write-ups, with the corrections stated
   plainly rather than folded into updated tables.

We will keep this page current as that proceeds.
