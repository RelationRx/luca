# Known issues

**Last updated: 2026-11-19. This list is not final — an audit is in
progress.**

A code review in November 2026 found defects in the benchmark engine and in
the analysis scripts that produce the numbers in our write-ups. We are
working through them in the open. This page records what is confirmed, what
is fixed, and what is still open.

An audit of the analysis layer has since added two further issues, and
corrected two earlier entries (10 and 11) that were described inaccurately
here. In both of those cases the correction makes the defect **smaller** than
we first reported.

**2026-11-19: issues 1, 4 and 12 are fixed in this repository.** A revealed
prediction task's answer can no longer be measured instead of predicted, each
task is scored once, and an intervention type the simulator cannot read is
refused instead of ignored. The three ship together: an unreadable type was a
silent no-op, so an agent could add a third gene with a fake type, change the
sealed combination and measure the held-out answer anyway. Results you
generated before this change are not comparable with results generated after
it. Record the commit you ran.

**2026-11-19: issue 13 is fixed in this repository.** An experiment the tool
layer cannot read is refused instead of quietly emptied. This is the change
most likely to affect what you measure.

## If you are using this repository

- **Do not compare models to each other using our published tables.** The
  tool layer silently discarded experiments from some models and not others
  (issue 13). This is the most serious issue on this page. The engine is
  fixed, but every published table predates the fix. Re-run before comparing.
- **Do not treat the easy or medium tiers as a test of non-additive causal
  reasoning.** Every prediction task at those tiers is solvable by measuring
  each gene separately and adding the effects (issue 2). The hard tier is
  not: about 55% of its tasks resist that strategy.
- **Do not rely on the published baseline numbers.** The heuristic baseline
  computed its own predictions with an inverted sign (issue 6).
- **Treat disease-mode results with particular care.** Signal-level
  malfunctions behave differently from the documentation (issue 5).
- **Re-run before you compare models.** The tool layer used to discard
  experiments it could not read (issue 13). It now applies the flat form and
  refuses everything else with an error, and an unreadable intervention *type*
  is refused too (issue 12). An agent that sent either shape will see errors
  where it previously saw normal-looking results. Every published table
  predates both fixes.
- **Results generated before these fixes are not comparable to results
  generated after.** Record the commit you ran, not just the seed.

If you are building on this benchmark and want to know whether a specific
issue affects you, open an issue and ask. We would rather answer than have
you discover it later.

## Confirmed issues

✅ fixed in this repository · ⚠️ fixed elsewhere, not yet here · ⬜ open

Four of eighteen are fixed here: issues 1, 4, 12 and 13.

| # | Issue | Affects | Status |
|---|---|---|---|
| 1 | `run_experiment` and `test_rescue` would execute a revealed prediction task's exact combination, so an agent could measure the answer instead of predicting it | held-out protocol | ✅ **fixed 2026-11-19** |
| 2 | Every easy and medium prediction task is solvable by a four-experiment additive strategy, contradicting the stated non-additivity guarantee | difficulty claims | ⬜ open — needs a generator change |
| 3 | `verify_organisms.py` looks up gene IDs in a dictionary keyed by gene names, silently reads every measured effect as zero, and so reports every task as non-additive | organism verification, seed screening | ⬜ open |
| 4 | `submit_prediction` disclosed ground truth and scored every retry, so a resubmitted answer raised the session average | scoring integrity | ✅ **fixed 2026-11-19** |
| 5 | Signal semantics disagree with the documentation in three ways: a bare `"activate"` resolves to the strength the simulator already uses and does nothing; the documented `{"type": "activate"}` form deactivates instead; an inhibitory `PERSIST` malfunction is negated twice and acts as strong activation | disease mode, signal diagnosis | ⬜ open |
| 6 | The heuristic baseline subtracted its own measured `BLOCK` delta instead of adding it, and treated `DAMPEN` as the opposite of `BLOCK` | baseline comparisons | ⚠️ **fixed**, not yet in this repo |
| 7 | The `v1-generation-freeze-2` tag named in `DECISIONS.md` predates a package rename and a vocabulary change, and does not reproduce current organisms | reproduction instructions | ⬜ open |
| 8 | `_composite_score` always divides by three in disease mode, so a run with a task subset is penalised for tasks it was not asked to perform | CLI subset runs only | ⬜ open |
| 9 | Diagnosis is scored on one irrevocable attempt while rescue takes the best of every attempt | diagnosis-rescue comparisons | ⬜ open — needs disclosure |
| 10 | **(corrected)** Five analysis scripts model a signal activation as a tenfold override. The live engine applies the signal's ordinary strength, and with the sign taken from the requested action rather than from the signal's mode | discriminating-evidence analysis | ⬜ open — measured effect smaller than first reported, see below |
| 11 | **(corrected)** The probe item builder uses the same tenfold, mode-signed convention as issue 10 when it constructs items about signal activation | probe studies | ⬜ open — **no item is mis-keyed**, see below |
| 12 | `run_experiment` never validates an intervention's type. An unrecognised type is silently ignored, costs one unit of budget, and returns no error | agent feedback, held-out protocol | ✅ **fixed 2026-11-19** |
| 13 | **The tool layer accepted intervention formats that it then ignored.** A request that did not use the documented `interventions` key reached the engine as an empty experiment: charged one unit of budget, returning the unperturbed organism and no error | **cross-model comparisons** | ✅ **fixed 2026-11-19** — see below |
| 14 | `report.py` renders a refused `test_rescue` as `restored=0%` with no error line, so a reader cannot tell a refused rescue from a failed one | session reports only | ⬜ open |
| 15 | `_generate_tasks` does not de-duplicate. Seed 10 medium produces `task_00` and `task_01` with the identical gene-and-type pair and different ground truth, so one organism asks the same question twice and scores it twice | prediction scoring | ⬜ open |
| 16 | The list intervention form accepts only `BLOCK`, `BOOST` and `DAMPEN`, so it cannot express a signal, and its refusal message never mentions signals. The dict form accepts `{"wave-X": "activate"}` | agent feedback | ⬜ open |
| 17 | `inspect.py` reads an intervention value of `"BLOCK"` as `""` when it colours the heatmap marker, so a string-valued intervention renders as a white `?`. Line 1443 reads the same value correctly | diagnostic figures only | ⬜ open |
| 18 | Nothing shows an agent that a signal goes in the interventions map. 78 of 18,356 stored calls asked for a signal-only experiment through shapes the engine does not read, such as `{"signal_activations": ["burst-I"]}` and `{"interventions": [], "signals": [...]}` | disease mode, signal diagnosis | ⬜ open |

Issues 1–8 came from the November 2026 review. Issues 9–11 were found while
investigating it. Issues 12 and 13 were found by a subsequent audit of the
analysis layer. Issues 14 and 15 were found by the code review of the issue 1
and 4 fix. Issues 16, 17 and 18 were found by the code review of the issue 13
fix, and 18 by a scan of the stored calls that followed it.

## ✅ Issues 1, 4 and 12, as fixed on 2026-11-19

Both changes make the engine refuse something it used to accept, so an agent
written against the old behaviour will now see errors where it previously saw
results. That is the point: the old behaviour failed in silence.

**Issue 1 — a revealed prediction task is held out.** `get_next_prediction_task`
now seals that task's exact gene-and-type combination. `run_experiment` and
`test_rescue` refuse it, and the refusal costs no budget. The seal lifts once
the task is answered. Running either of the task's genes on its own is still
allowed, and so is any other combination: measuring single genes and adding
the effects is a legitimate strategy, and the held-out quantity is the joint
outcome.

**Issue 4 — one scored answer per task.** `submit_prediction` still discloses
ground truth, so an agent can learn from it. A second submission for the same
task is now refused instead of scored.

**Issue 12 — an intervention type the simulator cannot read is refused.**
`dynamics.apply_interventions` matches `BLOCK`, `BOOST` and `DAMPEN` exactly
and has no else branch. Any other string fell through every branch, so the
gene was never perturbed, the call still cost a unit of budget, and the
readout came back looking normal. `_resolve_interventions` now refuses an
unreadable type, at no budget cost, and the call is not written to the
experiment log. Lower case used to be accepted and then ignored; it is now
normalised, so `{"type": "block"}` blocks the gene.

**Why these three ship together.** The issue 1 seal compares gene-and-type
pairs. While an unreadable type was a no-op, an agent could add a third gene
with a fake type: the combination no longer matched, the seal let the call
through, the fake type did nothing, and the readout was the task's own answer.
Measured on seed 0 medium, that route scored accuracy 1.0 and mse 0.0003. The
seal is only real once the type is validated.

The review of the issue 1 and 4 fix found four further defects. Three are
fixed here:

- A prediction naming none of the organism's phenotypes was scored from the
  `0.5` default and then locked by the issue 4 rule, which made a formatting
  slip permanent. Such an answer is now refused, costs nothing, and leaves the
  task open. One recognised phenotype is still enough.
- The seal ignored signals, so the task's genes under a changed signal — a
  different experiment with a different outcome — was refused. Signals are now
  part of the comparison.
- The seal iterated a `set`, against the determinism rule, and so could name
  the wrong task id when two tasks share a combination. It now iterates in
  sorted order. The duplicate itself is issue 15.

The fourth is issue 14, in `report.py`, and is not fixed here.

All rules are stated in the `run_experiment`, `test_rescue` and
`submit_prediction` tool descriptions, so an agent is told before it spends a
turn discovering them. Regression tests:

    pytest tests/test_experiment.py -k "HeldOut or Immutable or Seal or InterventionType or PredictionLabels"

## ✅ Issue 13, in detail

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

### As fixed on 2026-11-19

The tool layer now reads every shape a model actually sent, and refuses the
shapes it cannot read.

- A payload with no wrapper key is read as the intervention map itself, so the
  flat form `{"G001": "BLOCK"}` works.
- A wrapper key still wins when one is present, including when it is empty.
  `{"interventions": {}}` is a deliberate null experiment, not an invitation to
  read the rest of the call as genes.
- A value that is not a mapping is refused.
- A list is refused when **any** entry is unreadable. The partial case matters
  as much as the whole one. An experiment that silently runs on fewer genes
  than the model believes corrupts the session just as thoroughly.
- A call carrying no payload at all is refused, rather than run as an empty
  experiment. All 85 such calls came from models that also sent the flat form,
  and the agent text beside them announces an intervention that was then not
  sent. Treating that as a deliberate null experiment would preserve the
  original defect under a new name.
- `test_rescue` read one key name only, so it was narrower still. It now uses
  the same path.

Every refusal costs no budget and names the shape it could not read, so a
model is told rather than left to repeat the format for a whole session.

Measured over the 1,220 stored session logs, of 18,356 `run_experiment` and
`test_rescue` calls: 16,821 were wrapped, 1,450 were flat and 85 were empty.
Flat and empty came only from gpt-4o, gpt-4.1, gpt-5.1 and qwen-3.5.
claude-opus-4-6, claude-sonnet-4-6 and deepseek-v3 sent 9,008 calls between
them and used neither shape.

The two denominators on this page agree. The table above counts the 860 LLM
sessions. The 1,220 logs add the three baselines, which run no model:
860 + 3 x 120 = 1,220.

This change makes the engine refuse calls it used to accept and bill. A model
that sent an unreadable payload will now see errors where it previously saw
normal-looking results. That is the point: the old behaviour failed in silence.

### What four rounds of code review added

The fix was reviewed four times. Each round read the previous round's
changes, and most of what rounds two, three and four found had been introduced
by the fixes themselves, not by the original defect. That is the main lesson
of this page: a fix that widens what a component must understand widens what
can disagree.

**One reading, for the engine and the trace.** `report.py` read the
`interventions` key alone. Once the tool layer applied the flat form, a flat
experiment ran in the engine and then showed in the trace as an empty one,
beside the phenotype values it had moved. On seed 0, `{"G001": "BLOCK"}` moved
`replication-index` by -0.105 while the trace printed `run_experiment(∅)`, and
edge inference returned nothing. `luca/payloads.py` now holds that reading, and
both modules call it.

That reading also has to be canonical, because the engine normalises and the
trace did not. Three defects shared that one cause: the HTML schematic labelled
every string value `activate` while the engine applied `BLOCK`; a lowercase
`{"G001": "block"}` was applied by the engine and dropped by edge inference;
and a payload of `42` or `"BLOCK G001"` raised while rendering, on shapes the
engine now refuses and that will therefore appear in new logs. The shared
reader returns `{target: {"type": T}}` for any shape and `{}` for anything
unreadable. A gene type is upper-cased. A signal action keeps its case, because
`report.py` colours `"activate"` by that exact string. A payload sent as a JSON
string is decoded in that one place, so the engine and the trace cannot
disagree about it.

**A refusal has to teach, and must not teach the wrong thing.** 472 stored
calls used an alternative container, such as `{"BLOCK": ["G001"]}` or
`{"perturbations": {...}}`. Every one ran as an empty experiment and was
billed; none returned an error. They are refused now, and the message names the
`interventions` key.

Two drafts of those messages were themselves defects. One told the model to
send `{"interventions": {"wave-X": "activate"}}`; for every signal on seed 0
that is bit-identical to a null experiment and still costs budget, because
`activate` resolves to the strength the simulator already uses (issue 5). The
four stored empty-list calls were signal-only requests, so that advice would
have sent exactly that audience into a billed no-op — the failure this fix
removes. The other fired on a flat call the layer had read correctly, telling a
model whose only fault was one wrong gene name to re-send under the wrapper,
which fails in the same way. The hint now fires only when no target in the
payload was recognised.

**Nothing refused may crash.** `dispatch_tool` is called without a guard, so an
exception ends the session rather than the call. A list entry whose target was
unhashable, such as `{"gene": ["G001"], "type": "BLOCK"}`, raised `TypeError`.
`submit_malfunction_hypothesis` read its keys by index and raised `KeyError` on
a missing one. "Refused, not emptied" must not become "crashed".

**No error may hide a better one.** A malformed payload masked
"submit_malfunction_hypothesis() must be called first", "not a disease
organism" and "Budget exhausted". The agent fixed the payload, resent the call,
and only then learned the real blocker, at one turn each time.
`ExperimentSession.rescue_state_error()` and `budget_error()` answer those
questions once, for the engine and the tool layer alike.

**Two payload shapes were decided on the evidence.** An empty list is refused:
all four stored empty-list calls were `{"interventions": [], "signals": [...]}`,
a signal-only experiment that ran as a null one and was billed.
`{"interventions": {}}` is still the explicit null experiment. A null wrapper
falls through to the alternate key, as the original `or` did; no stored call
sent one, but a null is an absent payload, not an empty one.

**One reading means one reading.** The fourth round reviewed
`luca/payloads.py` alone and found that the module written to hold a single
reading held two. `canonical_interventions` carried its own copy of the rule
for reading one list entry, and the copy disagreed with the engine on key
precedence:

    [{"target": "G001", "gene": "G002", "mode": "BOOST"}]
        engine G001   trace G002
    [{"gene": "G001", "action": "BOOST", "mode": "BLOCK"}]
        engine BOOST  trace BLOCK

The first names a gene the engine never perturbed. The second inverts an
inferred edge, because the discovered network maps a positive change to
opposite directions for `BLOCK` and `BOOST`. `entry_target` and `entry_action`
now live in one place and both readers call them. A test compares the trace
against `_resolve_interventions`, which is the last word on what the simulator
perturbs.

The same round found three more: a list entry with no readable action rendered
as a real `BLOCK` while the engine refuses the call; an invented container was
drawn as a target, so 472 stored calls showed a gene called `perturbations` or
`BLOCK`; and a payload delivered as a bare string raised rather than being
read, which ended the session.

It also asked whether one rule was intended, and it was not. With
`{"interventions": {}, "gene_interventions": {...}}` the key-presence rule ran
an empty experiment and billed for it, where the original `or` chain ran the
populated map. A populated wrapper now wins. A call where every wrapper present
is empty is still a deliberate null experiment.

Three further findings are recorded as issues 16, 17 and 18, and are not fixed
here.

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
2. Land the remaining engine fixes. Issues 1, 4, 12 and 13 are done; issue 3
   is next.
3. Recompute every affected number, and re-run the sessions that the
   held-out protocol change invalidates.
4. Post corrected versions of the write-ups, with the corrections stated
   plainly rather than folded into updated tables.
