# Known issues

**Last updated: 2026-11-20. This list is not final — an audit is in
progress.**

A code review in November 2026 found defects in the benchmark engine and in
the analysis scripts that produce the numbers in our write-ups. We are
working through them in the open. This page records what is confirmed, what
is fixed, and what is still open.

An audit of the analysis layer has since added two further issues. Two earlier
entries, 10 and 11, have been **withdrawn**: they described defects in analysis
scripts that are not part of this repository, so a reader here could neither
see them nor reproduce them. The numbering is unchanged, because merged pull
requests cite it.

Each issue below now carries a **bucket**. **v1** means it must be fixed before
other people can use this environment, and we are fixing those now. **v2**
means it is known and recorded, and it is resolved in the LUCA v2 redesign.
Several v1 fixes change the numbers. We say so rather than preserve a number we
know to be wrong.

**2026-11-19: issues 1, 4 and 12 are fixed in this repository.** A revealed
prediction task's answer can no longer be measured instead of predicted, each
task is scored once, and an intervention type the simulator cannot read is
refused instead of ignored. The three ship together: an unreadable type was a
silent no-op, so an agent could add a third gene with a fake type, change the
sealed combination and measure the held-out answer anyway. Results you
generated before this change are not comparable with results generated after
it. Record the commit you ran.

**2026-11-19: issue 3 is fixed in this repository.** The additivity verifier
reported every prediction task at every tier as non-additive. It does not. The
corrected measurement over seeds 0-19 is **easy 40 of 40, medium 40 of 40,
hard 18 of 40** additively solvable against the ground truth the engine stores,
and **easy 40 of 40, medium 40 of 40, hard 34 of 40** against a noise-free
ground truth. Both are reported below, with the question each one answers.
Either way the easy and medium tiers are fully additive, which is the evidence
for issue 2.

**2026-11-20: issue 6 is fixed in this repository.** The heuristic baseline
subtracted its own measured delta instead of adding it. Over seeds 0-9 its mean
accuracy goes from 0.7167 to 0.9333 on easy, 0.5500 to 0.8167 on medium, and
0.3500 to 0.6667 on hard. Every published baseline number predates this.

**2026-11-20: issues 19 and 5a are fixed in this repository.** A persistent
inhibitor now inhibits, and the rescue the generator certifies for a `PERSIST`
malfunction can now be performed. Both change what disease mode does. The
canonical disease organisms are not the same organisms they were: 11 of the 60
carry a different malfunction. Disease results you generated before this change
do not compare with results generated after it.

**2026-11-20: issue 20 is fixed in this repository.** A bare `pytest` from the
repository root was importing a different checkout's engine, so the tests that
prove issues 1, 4 and 12 are fixed were failing under the documented command.
If you have run this suite before, run it again.

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
  each gene separately and adding the effects (issue 2). The hard tier is the
  only one that resists, and it resists less than it looks: 22 of its 40 tasks
  defeat an additive strategy against the stored ground truth, but only about 6
  of those do so because of the dynamics. The rest is readout noise. See
  issue 3 below for both numbers.
- **Do not rely on the published baseline numbers.** The heuristic baseline
  computed its own predictions with an inverted sign (issue 6, fixed
  2026-11-20). On medium it spent 20 experiments, and on hard 15, to score
  **below** a baseline that runs none. Every published heuristic number
  predates the fix.
- **Do not compare disease results across 2026-11-20.** Issues 19 and 5a are
  fixed, and the fix changes which organisms the generator produces. 11 of the
  60 canonical disease organisms now carry a different malfunction, and the
  number carrying a `PERSIST` malfunction rises from 9 to 12. Every stored
  disease result predates this. Gene malfunctions, `LOCK_HI` and `LOCK_LO`,
  behave as they did.
- **`activate` is now refused, not ignored.** `deactivate` is the only signal
  verb the engine accepts, and both the bare string and the `{"type": ...}`
  form work. An agent that sends `activate` gets an error instead of a
  normal-looking result from an experiment that did nothing. What `activate`
  *should* mean is still open (issue 5b, v2): every signal is already on at its
  own strength, so the verb has no referent.
- **A held-out prediction task's answer is still reachable (issue 21).** Resend
  a revealed task's exact gene pair together with one unrelated signal change,
  and the call runs and returns the answer. Issue 1 closed the bare
  combination, and that stays closed. This is the escape that finding 3 of the
  PR #9 review then opened on purpose. Measured on the code before the issue 5a
  fix, both signal verbs leaked at all three tiers, so nothing about this is new
  on 2026-11-20. **It is a v2 item**, because signal prediction is being
  redesigned and the seal's rule for signals belongs to that design. Until it is
  closed, **treat a prediction score as an upper bound**, and say so when you
  report one.
- **Check which `luca` your tests import.** Until 2026-11-20 a bare `pytest`
  here could import a different checkout (issue 20). Run
  `python -c "import luca; print(luca.__file__)"` and confirm the path is
  inside your own checkout.
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

Every issue carries a **bucket**:

- **v1** — it must be fixed before other people can use this environment. We
  are fixing these now. Some of these fixes change the numbers, and we say so
  rather than preserve a number we know to be wrong.
- **v2** — it is known and recorded, and it is resolved in the LUCA v2
  redesign. These need a generator change or a decision about what the API
  should mean, not a bug fix.

**The table is sorted by bucket: every v1 issue first, then v2.** Within each
bucket it is in issue-number order, so the numbers are not consecutive.

Nine of the twenty rows below are fixed here: issues 1, 3, 4, 5a, 6, 12, 13,
19 and 20. Eleven are open: six in v1 and five in v2.
The count is of rows, not of original issue numbers: issue 5 is split into 5a
and 5b, and 10 and 11 are withdrawn.

Issues 10 and 11 have been withdrawn from this list. They described defects in
analysis scripts that are not part of this repository, so a reader here could
neither see them nor reproduce them. The numbering is unchanged, because merged
pull requests cite it, so the table skips from 9 to 12.

| # | Issue | Bucket | Affects | Status |
|---|---|---|---|---|
| 1 | `run_experiment` and `test_rescue` would execute a revealed prediction task's exact combination, so an agent could measure the answer instead of predicting it | v1 | held-out protocol | ✅ **fixed 2026-11-19** |
| 3 | `verify_organisms.py` looks up gene IDs in a dictionary keyed by gene names, silently reads every measured effect as zero, inverts the sign of the effects it does measure, and measures only `BLOCK`. It reported every task at every tier as non-additive | v1 | organism verification, seed screening | ✅ **fixed 2026-11-19** — see below |
| 4 | `submit_prediction` disclosed ground truth and scored every retry, so a resubmitted answer raised the session average | v1 | scoring integrity | ✅ **fixed 2026-11-19** |
| 5a | The chronic malfunction signal override was negated twice. Five sites stored a value already signed for an inhibiting signal, and `luca/dynamics.py:50` applied the mode sign again. A persistent **inhibitor** therefore simulated as a strong **activator** | v1 | disease mode | ✅ **fixed 2026-11-20** — see below |
| 6 | The heuristic baseline subtracted its own measured `BLOCK` delta instead of adding it, and treated `DAMPEN` as the opposite of `BLOCK`. Over seeds 0-9 it therefore scored **below** a baseline that runs no experiments at all, on medium and on hard | v1 | baseline comparisons | ✅ **fixed 2026-11-20** — see below |
| 7 | The `v1-generation-freeze-2` tag named in `DECISIONS.md` predates a package rename and a vocabulary change, and does not reproduce current organisms | v1 | reproduction instructions | ⬜ open |
| 8 | `_composite_score` always divided by three in disease mode, so a run with a task subset was penalised for tasks it was not asked to perform. `--tasks predict diagnose` with accuracy 0.8 and diagnosis 0.5 scored **0.4333 instead of 0.65** | v1 | CLI subset runs only | ✅ **fixed 2026-11-22** — see below |
| 9 | Diagnosis is scored on one irrevocable attempt while rescue takes the best of every attempt | v1 + v2 | diagnosis-rescue comparisons | ⬜ open — v1 documents the asymmetry; v2 decides whether to change it |
| 12 | `run_experiment` never validates an intervention's type. An unrecognised type is silently ignored, costs one unit of budget, and returns no error | v1 | agent feedback, held-out protocol | ✅ **fixed 2026-11-19** |
| 13 | **The tool layer accepted intervention formats that it then ignored.** A request that did not use the documented `interventions` key reached the engine as an empty experiment: charged one unit of budget, returning the unperturbed organism and no error | v1 | **cross-model comparisons** | ✅ **fixed 2026-11-19** — see below |
| 14 | `report.py` renders a refused `test_rescue` as `restored=0%` with no error line, so a reader cannot tell a refused rescue from a failed one | v1 | session reports only | ⬜ open |
| 15 | `_generate_tasks` looped `n` times and never compared a new task against the tasks already built, so one organism could ask the same question twice. **The duplicate broke the issue 1 seal**: answer `task_00`, run that exact experiment unsealed, then reveal the identical `task_01` and submit the measured values. On medium seed 10 that scored **accuracy 1.0, mse 0.0001** for 1 unit of budget. Measured over seeds 0-299 at three tiers: **7 of 900** organisms carried an exact duplicate, and medium seed 10 carried one inside the canonical 60. An earlier entry here claimed no organism of the 60 carried a duplicate; that measurement compared dictionary key order, and 6 of the 7 duplicates reverse it | v1 | **held-out protocol**, prediction scoring | ✅ **fixed 2026-11-21** — see below |
| 17 | `inspect.py` reads an intervention value of `"BLOCK"` as `""` when it colours the heatmap marker, so a string-valued intervention renders as a white `?`. Line 1443 reads the same value correctly | v1 | diagnostic figures only | ⬜ open |
| 19 | `test_rescue` re-applied the chronic signal override after it read the agent's request, so the rescue the generator certifies for a `PERSIST` malfunction could not be performed. Measured before the fix: 9 of the 60 canonical disease organisms carried a `PERSIST` malfunction, all 9 were certified rescuable, and all 9 returned `restored_fraction = 0.0` | v1 | disease mode, rescue scoring | ✅ **fixed 2026-11-20** — see below |
| 20 | `pytest` run from the repository root imported `luca` from a different checkout. There is no `conftest.py` and no pytest path setting, and pytest's `prepend` import mode puts the *test file's* directory on `sys.path`, never the repository root. An editable install of `luca` elsewhere therefore won. The tests that prove issues 1, 4 and 12 are fixed were failing under the documented command | v1 | every test run | ✅ **fixed 2026-11-20** — see below |
| 2 | Every easy and medium prediction task is solvable by a four-experiment additive strategy, contradicting the stated non-additivity guarantee. A session asks two tasks of two genes each, so measuring those genes separately and adding the effects answers both. Measured over seeds 0-19: easy 40 of 40, medium 40 of 40, hard 18 of 40 against the stored ground truth, and 34 of 40 noise-free — see issue 3 for which number answers which question | v2 | difficulty claims | ⬜ open — needs a generator change |
| 5b | What `activate` should mean is undecided. Every signal is already on at `sig.strength`, so the verb has no referent. Since 2026-11-20 the engine refuses it rather than ignoring it, and `deactivate` works in both forms (issue 5a). Deciding what an agent should be able to *do* to a signal beyond switching it off is a design question, not a bug | v2 | disease mode, signal diagnosis | ⬜ open |
| 16 | The list intervention form accepts only `BLOCK`, `BOOST` and `DAMPEN`, so it cannot express a signal, and its refusal message never mentions signals. The dict form accepts `{"wave-X": "deactivate"}` | v2 | agent feedback | ⬜ open |
| 18 | Nothing shows an agent that a signal goes in the interventions map. 78 of 18,356 stored calls asked for a signal-only experiment through shapes the engine does not read, such as `{"signal_activations": ["burst-I"]}` and `{"interventions": [], "signals": [...]}` | v2 | disease mode, signal diagnosis | ⬜ open |
| 21 | **The issue 1 seal has a deliberate escape, and the escape leaks.** Finding 3 of the PR #9 review made `_sealed_task_for` return `None` whenever the agent changes any signal, on the reasoning that the same genes under a changed signal is "a different experiment with a different outcome". The outcome is not different enough. A revealed task's exact gene pair plus one unrelated signal change runs and returns the held-out answer. Worst gap against the stored ground truth, against a scoring threshold of 0.10 — before the issue 5a fix: easy 19 **0.0150**, medium 16 **0.0199**, hard 12 **0.0913**; after it: **0.0253**, **0.0522**, **0.0913**. Closing it in v1 costs five lines, and `tests/test_experiment.py::TestSealCoversSignals` is the test that would change. We are not doing that, because signal prediction is being redesigned in v2 and the seal's rule for signals should follow that design, not precede it | v2 | **held-out protocol** | ⬜ open |

Issues 1–8 came from the November 2026 review. Issue 9 was found while
investigating it. Issues 12 and 13 were found by a subsequent audit of the
analysis layer. Issues 14 and 15 were found by the code review of the issue 1
and 4 fix. Issues 16, 17 and 18 were found by the code review of the issue 13
fix, and 18 by a scan of the stored calls that followed it. Issues 19 and 20
were found on 2026-11-20 while planning the remaining v1 work. Issue 21 was
found by the code review of the issue 19 and 5a fix.

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

## ✅ Issue 3, as fixed on 2026-11-19

This one changes a published number rather than the engine's behaviour.

`check_additivity` builds an additive prediction for each task and asks whether
it lands within the scoring threshold. It was wrong in two ways, and either one
alone was enough to make every answer the same:

- It looked up `gene.id` (`g_019`) in a dictionary keyed by `gene.name`
  (`G019`). The two never overlap, so every measured effect fell back to `0.0`
  and the additive prediction was just the unperturbed baseline.
- It multiplied a measured `BLOCK` delta by `-1.0`, although the measured
  quantity is already a delta, and it measured only `BLOCK` even when the task
  asked for `BOOST` or `DAMPEN`.

The verifier therefore reported every task at every tier as non-additive, which
is where the published rate of 0.00 came from.

The corrected verifier measures each of a task's genes on its own, under the
intervention type the task asks for, adds those deltas to the baseline, and
clips once at the end so the order of the genes cannot change the answer. It
takes its baseline from `_readout_noise_free_phenotypes` so that the baseline
and the perturbed runs come from the same simulation path and the same rng
stream.

An earlier version of this page said that baseline was chosen in preference to
"the noisy `get_info()["baseline_phenotypes"]`". That was wrong, and we are
correcting it rather than quietly deleting it: `get_info()` is **not** noisy —
`_compute_baseline_phenotypes` passes `noise=False`. It simply reads
`organism.baseline_state` instead of re-simulating, so it is not the same
comparison.

Measured over seeds 0-19. **Two numbers, because there are two questions:**

| Tier | As the engine ships | Against a noise-free ground truth |
|------|---------------------|-----------------------------------|
| Easy | **40 of 40** | **40 of 40** |
| Medium | **40 of 40** | **40 of 40** |
| Hard | **18 of 40** | **34 of 40** |

The first column answers "how often does an additive strategy score as correct
against the answer the engine actually stores?" The second answers "how often
is the task additive in the underlying dynamics?"

They differ at the hard tier because `task.ground_truth` carries readout noise
of `rng.normal(0, noise_sigma * 2)` (`luca/dynamics.py:120`). At the hard tier
that noise has mean 0.072 and maximum 0.164, against a threshold of 0.10. So
most of the 16-task gap is noise, not sigmoid interaction. Roughly 6 of the 22
hard tasks that the first column calls non-additive resist an additive
strategy for the reason the design intends.

Neither column changes the easy or the medium result. So neither changes
issue 2.

`tests/test_verify_organisms.py` measures the first column twice: once through
`verify_organisms.py` and once through a second path inside the test file. That
second path is **not** independent, and an earlier version of this page said it
"shares none of its code". It copies `_readout_noise_free_phenotypes` and its
`default_rng(0)` stream, so a conceptual error common to both is invisible to
it — and one was. Neither path noticed the readout noise above. It checks the
arithmetic, not the concept. Reproduce with
`pytest tests/test_verify_organisms.py`.

`check_additivity` now refuses a disease organism rather than answering.
`_readout_noise_free_phenotypes` passes `active_signals={}`, so a chronic
`PERSIST` override is dropped from the additive model but not from
`task.ground_truth`, and the comparison would be between two different
organisms. This is latent today, because `verify_organism` builds only healthy
organisms. It is a refusal, not a fix.

Every lookup in `check_additivity` that used to carry a default — `.get(gene_id,
{})`, `.get(ph, 0.0)`, `.get(ph, 0.5)`, `.get("type", "BLOCK")` — now raises.
Those defaults are the same silent-zero mechanism that caused this issue. Two
more in `_noiseless_single_gene_effects` and the latent check are gone for the
same reason, although neither was reachable.

**One output change.** The per-task `interventions` key in the screening
`.jsonl` now carries the gene *name* (`G019`) rather than the gene *id*
(`g_019`). That is the identifier the rest of the page and the agent-facing API
use. If you compare a screening run from before 2026-11-19 with one from after,
the keys differ.

**What this means for the benchmark.** The easy and medium tiers do not test
non-additive causal reasoning. Every task at both tiers is solvable by
measuring the genes separately and adding the effects. Only the hard tier
resists it, and only for 22 of its 40 tasks. That is issue 2, and it is a
property of the generator rather than a bug in this file, so it waits for
LUCA v2. `docs/benchmark_design.md` claimed trivially additive tasks were
"guaranteed to be absent"; it no longer does.

One further repair in the same file: `REPO_ROOT` was
`Path(__file__).parent.parent.parent`, left over from when this script lived
under `experiments/paper_v1/`. It pointed two directories above the repository.
Running the script directly still worked, because Python puts the script's own
directory first, but any other entry point could import a different copy of
`luca`.

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
unreadable. A gene type is upper-cased. A signal action keeps its case, so the rendered
trace shows the verb the agent sent. (That reason was first written here as
"`report.py` colours `"activate"` by that exact string". It never did: a signal
node has never used that colour map. Corrected 2026-11-20.) A payload sent as a JSON
string is decoded in that one place, so the engine and the trace cannot
disagree about it.

**A refusal has to teach, and must not teach the wrong thing.** 472 stored
calls used an alternative container, such as `{"BLOCK": ["G001"]}` or
`{"perturbations": {...}}`. Every one ran as an empty experiment and was
billed; none returned an error. They are refused now, and the message names the
`interventions` key.

Two drafts of those messages were themselves defects. One told the model to
send `{"interventions": {"wave-X": "activate"}}`; for every signal on seed 0
that was bit-identical to a null experiment and still cost budget, because
`activate` resolved to the strength the simulator already uses (issue 5). Since
2026-11-20 `activate` is refused outright and `deactivate` is the verb that
works (issue 5a). The
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

## ✅ Issue 20, as fixed on 2026-11-20

**The test suite was not testing this repository.**

`luca` is installed in editable mode, and on the machine this was found on the
install pointed at a different checkout. pytest's default `prepend` import mode
puts the *test file's* directory on `sys.path`, never the repository root, and
this repository had no `conftest.py` and no `[tool.pytest.ini_options]`. So a
bare `pytest` from the repository root imported the other checkout's engine.

Under pytest, before the fix:

    sys.path[0]     <repo>/tests
    luca.__file__   <the other checkout>/luca/__init__.py

That other engine has no `_sealed_task_for`; this one has three. So the tests
that prove issues 1, 4 and 12 are fixed were not passing under the command this
page and `CLAUDE.md` tell you to run:

    pytest tests/test_experiment.py -k "seal or held"
      before    7 failed, 6 passed
      after    13 passed

`conftest.py` now prepends the repository root and then asserts that `luca`
resolved inside it, so a wrong resolution fails loudly instead of quietly
measuring different code. `tests/test_verify_organisms.py` carries the same
assertion as a test, because that file is also run on its own.

Full suite against this repository's engine: **245 passed**. Any suite count
recorded on this page or in the repository before 2026-11-20 was not produced
by a bare `pytest -q` and is not reproducible with one.

If you have run this suite before, re-run it. If you build on this repository,
check that `python -c "import luca; print(luca.__file__)"` prints a path inside
your own checkout.

## ✅ Issues 19 and 5a, as fixed on 2026-11-20

One defect, seen twice. Both halves are about a single number: the value stored
in an `active_signals` entry when a `PERSIST` malfunction jams a signal on.

### The convention

`luca/dynamics.py` documents an `active_signals` entry as a value that
"overrides `signal.strength`", and then applies the signal's mode sign to it:

    strength = active_signals.get(sig.id, sig.strength)
    signed   = strength if sig.mode == "activates" else -strength

So an entry is an **unsigned magnitude**. Five places wrote a value that was
already signed, and the sign landed twice.

- `luca/generation.py` — the screener that decides which signals can carry a
  `PERSIST` malfunction
- `luca/generation.py` — the malfunction that ships
- `luca/generation.py` — the alternative-malfunction ambiguity check
- `luca/experiment.py` — the session's mirror of the chronic override
- `luca/experiment.py` — `_resolve_interventions`, where the agent's own verb
  is read

`luca/dynamics.py` was always right and is unchanged.

### What it looked like

At seed 0, medium, the signal `potential-theta` **inhibits** `g_007` and
`g_018` with strength 0.5960. A `PERSIST` malfunction amplifies it ten times.

| gene | healthy | jammed, before the fix | jammed, after the fix |
|---|---|---|---|
| `g_007` | 0.0968 | 0.9944 | 0.0102 |
| `g_018` | 0.9322 | 1.0000 | 0.0601 |

A persistent inhibitor drove its targets to the ceiling.

### The rescue

`generate_disease_organism` ships a `PERSIST` malfunction only after it has
verified that deactivating the signal restores an aberrant phenotype. That
rescue could not be performed. `test_rescue` re-applied the chronic override
after reading the agent's request, so the certified cure scored
`restored_fraction = 0.0`, and so did everything else.

The rule itself is right; it was applied in one place too many.
`run_experiment` keeps it, because an agent exploring the organism must not be
able to switch the disease off. `test_rescue` is the call that proposes the
cure, so there the agent may switch it off. A signal named in `test_rescue`
that is also the malfunctioning one is dropped from both the agent's map and
the chronic map, which returns it to its normal strength — the state the
generator certifies. Cancelling is per call: the session's record of the
disease is not edited, so the next call is diseased again.

### The signal verb

`_resolve_interventions` read the verb as
`1.0 if val in ("activate", "activates") else -1.0`. A dict never equals either
string, so the documented `{"wave-X": {"type": "deactivate"}}` form fell to
`-1.0` along with everything else. And `-1.0 * strength` does not switch a
signal off: with the mode sign applied on top, an activator became an inhibitor
of equal size.

Off is now `0.0`, and both the bare string and the `{"type": ...}` form work.

**`activate` is now refused rather than silently ignored.** Every signal is
already on at its own strength, so the verb has no referent. What it should
mean is issue 5b, which is open and belongs to the v2 redesign. The error names
`deactivate` and points at 5b. A refused call costs no budget.

### What moved

The screener now accepts a different set of signals, so the canonical disease
organisms are not the same organisms.

- **11 of the 60** disease organisms in seeds 0-19 carry a different
  malfunction.
- Organisms carrying a `PERSIST` malfunction rise from **9 to 12** of 60. Eleven
  sit on an inhibiting signal; one, hard seed 0, sits on an activating signal.
- All 12 reach `restored_fraction = 1.0` by deactivating the malfunctioning
  signal. Before the fix, all 9 returned `0.0`.

Nothing in the test suite pinned the old sign or the identity of a disease
organism. That is why the defect survived. The suite was 245 passed before this
change and **279 passed** after it, the difference being the new tests.

The renderer reads stored session logs and carries two consequences. The signal
node in the schematic printed a hardcoded `act` beside any signal the agent
touched, which now says the opposite of what happened; it shows the verb sent.
And causal direction inference matched no branch for `deactivate`, so the edge
was silently dropped; `deactivate` now joins the `BLOCK` family, because
switching a signal off takes its input away exactly as blocking a gene does.
`activate` is still read, because logs recorded before this fix contain it.

## ✅ Issue 6, as fixed on 2026-11-20

**The baseline that spends budget scored worse than the one that does not.**

The heuristic measures each gene's effect by `BLOCK`ing it and recording
`result - baseline`. It then **subtracted** that delta when predicting a
`BLOCK`, so every measured decrease became a predicted increase. `DAMPEN` was
treated as the opposite of `BLOCK`, although `DAMPEN` clamps the gene to at
most 0.15, which is nearly the `BLOCK` state.

Mean prediction accuracy over seeds 0-9, measured in this repository:

| tier | before | after | random, 0 experiments |
|---|---|---|---|
| easy | 0.7167 | **0.9333** | 0.6667 |
| medium | 0.5500 | **0.8167** | 0.6500 |
| hard | 0.3500 | **0.6667** | 0.4667 |

On medium and hard the heuristic landed below a baseline that runs none, after
spending its whole sweep: 20 experiments on medium, and 15 on hard, where only
15 genes are observable. Nothing asserted that it should not. That assertion is
now a test, at both tiers.

The arithmetic lives in `_additive_prediction`, so it can be tested without
running a session. `BLOCK` and `DAMPEN` reuse the measured delta; `BOOST`
opposes it. **The `BOOST` magnitude is an estimate, not a calibration.** Agents
never see gene states, so the baseline activity a `BOOST` moves away from is
unknown. Reusing the `BLOCK` magnitude is the best available guess. This
baseline exists to show what a non-adaptive additive rule achieves, not to be
the strongest possible one.

None of the five existing heuristic tests caught this. They check shapes and
relative orderings rather than numbers, and the one comparative test used the
easy tier, where the defect does least harm. Six tests now pin the arithmetic
against hand-computed values.

`docs/custom_agents.md` taught the same inverted rule in its worked example and
is corrected.

## ✅ Issue 15, as fixed on 2026-11-21

### What the duplicate did

`_generate_tasks` built `n` tasks in a loop. It never compared a new task
against the tasks it had already built, so one organism could ask the same
question twice.

That is not only a scoring nuisance. It reopens issue 1. `_sealed_task_for`
locks a task only while that task is revealed and unanswered, so a duplicate
is reachable in three steps:

1. Reveal `task_00`, answer it, and unseal the combination.
2. Run that exact experiment. The engine does not refuse it, because the only
   task holding that signature has been answered and the identical `task_01`
   has not been revealed yet.
3. Reveal `task_01`, which is the same question, and submit the measured
   values.

On medium seed 10, step 3 scored **accuracy 1.0, mse 0.0001** for 1 unit of
budget. The agent measured the held-out answer instead of predicting it.

### How often it happened

Measured over seeds 0-299 at all three tiers, 900 organisms:

| measure | before | after |
|---|---|---|
| exact duplicates — same genes and same types | **7 of 900** | **0 of 900** |
| same gene pair, different types | 43 of 900 | 36 of 900 |

Easy carried none. Medium carried three, at seeds 10, 137 and 239. Hard
carried four, at seeds 61, 137, 155 and 195. Inside the canonical 60, seeds
0-19, only **medium seed 10** carried a duplicate.

A repeated gene pair under different intervention types asks a different
question, so 36 of 900 is correct and is not a defect. The count fell by
exactly the 7 exact duplicates.

### Why this file said the defect was absent

The previous entry claimed that no organism of the 60 carried a duplicate, and
that an earlier note naming medium seed 10 did not reproduce. Both claims were
false, and the note was right.

The measurement behind them compared the interventions in dictionary key
order. Six of the seven duplicates reverse that order:

```
task_00  {'g_013': BOOST, 'g_016': DAMPEN}
task_01  {'g_016': DAMPEN, 'g_013': BOOST}
```

An order-sensitive comparison therefore reported "0 of 60". `ExperimentSession`
already held the correct comparison: `_intervention_signature` returns a
`frozenset`, so the seal had always seen through the key order. Only the
measurement did not.

### The fix

A candidate whose signature repeats a task already built is rejected, and the
retry loop draws again. The check runs **before** `simulate_sigmoid`, so a
rejected candidate costs no simulation, and an organism that never collides
draws no extra numbers and keeps its exact identity.

It reuses `_intervention_signature`, the function the seal uses. The generator
and the seal therefore cannot drift apart on what "the same experiment" means.

The set of signatures is seeded from the tasks that already exist, not left
empty. A second `_generate_tasks` call with a smaller `n` overwrites the low
ids and leaves the high ones in place, so an empty set would let a rebuilt task
repeat a surviving one. Easy seed 6 did exactly that. The code review of this
fix found it.

When no distinct candidate appears within `max_retries`, the generator raises
and names the seed, the difficulty and `n`. It does not emit the duplicate.
No organism measured reaches that path; a request for more tasks than the
observable gene pool can supply does.

### What moved

Medium seed 10 is the only canonical organism this fix changed. Its `task_01`
is now `{'g_014': DAMPEN, 'g_015': BOOST}`, a different question from
`task_00`. Running `task_00`'s combination and submitting those values for
`task_01` now scores **accuracy 0.3333, mse 0.0334**.

**The additivity anchors did not move**: easy 40 of 40, medium 40 of 40, hard
18 of 40 as the engine ships, and 40, 40 and 34 against a noise-free ground
truth.

`tests/test_experiment.py::TestSealNamesTheLowestMatchingTask` asserted that
seed 10 medium "must still generate the duplicate pair". No seed does now, so
it builds the pair by hand. Its comment called the duplicate "latent, not
observable"; that was wrong, and the new comment records why.

## ✅ Issue 8, as fixed on 2026-11-22

### What it did

`_composite_score` built a three-element component list in disease mode,
whatever the run asked for:

```python
diag   = record.get("diagnosis_score") if "diagnose" in active_tasks else None
rescue = record.get("rescue_fraction") if "rescue" in active_tasks else None
components = [acc, diag if diag is not None else 0.0,
              rescue if rescue is not None else 0.0]
return round(sum(components) / len(components), 4)
```

Two different situations collapsed to the same `0.0`:

1. the task was **never requested** — it must be excluded from the average;
2. the task **was requested** and the model did not attempt it — it must
   count as `0.0`, because not attempting is a failed attempt.

The docstring already stated that split. The code did not implement it. A
`--tasks predict diagnose` run with accuracy 0.8 and diagnosis 0.5 therefore
scored `(0.8 + 0.5 + 0.0) / 3 = 0.4333` instead of `(0.8 + 0.5) / 2 = 0.65`.
That is a 33% penalty for a rescue the run never asked for.

`--tasks` is a documented CLI argument (`evaluate.py:374`), so this is a
supported path, not a hypothetical one.

**`--tasks predict rescue` is a weaker example, and this file used to give it.**
Rescue is gated on a locked malfunction hypothesis
(`luca/experiment.py:704`), and the hypothesis tool is only offered when
`diagnose` is active (`luca/agent.py:351`). Both built-in baselines gate on
`session._hypothesis_locked` too, and `evaluate.py:431` prints a warning for
exactly this combination. So through any built-in runner that combination
always leaves `rescue_fraction = None`, and the change is 0.2667 → 0.40, not
0.4667 → 0.70. Only a custom `--agent` calling the session directly reaches a
real rescue fraction there.

### The mechanism

`record.get("diagnosis_score")` returns `None` both when the key is absent and
when the task was not requested, and both became `0.0`. This is the pattern
`CLAUDE.md` already names as the mechanism behind issue 3: a `.get(...,
default)` that turns a missing measurement into a confident number.

The fix indexes directly. `_make_record` always writes both keys in disease
mode, so a missing key now raises `KeyError` instead of scoring zero. The
per-seed `except` in `run_evaluation` catches it and records that seed as an
error, so the seed is reported as failed rather than scored from a value
nobody measured.

### What moved

**No published number.** A full run has all three tasks active, so the
component list is still three long and every existing score is unchanged. Only
subset runs change, and no published result used one.

### Coverage

`_composite_score` had **no tests at all** before this change.
`tests/test_evaluate.py` now pins ten cases with hand-computed values,
including the two that used to be indistinguishable: the same record scored
under `--tasks predict rescue` and under a full run must give 0.70 and 0.4667,
not one number.

## Reproducing any of these

The reproduction scripts live in the development repository and will be
mirrored here with the fixes. Each issue above was confirmed by direct
measurement, not by inspection alone.

## What happens next

1. ~~Finish auditing the analysis scripts.~~ A first pass is done; it produced
   issues 12 and 13. The scaling-study logs and several analysis scripts are
   still unexamined.
2. **Land every v1 fix.** Issues 1, 3, 4, 5a, 6, 8, 12, 13, 15, 19 and 20 are done.
   19 and 5a shipped together, because fixing either alone leaves the rescue
   broken. 15 landed on 2026-11-21 and 8 on 2026-11-22. The order from here is
   14, 7, 17, and finally the disclosure for 9. Issue 21 was found by the review of 19 and 5a and moved to
   v2 on 2026-11-20: it is a real hole, but signal prediction is being
   redesigned, and the seal's rule for signals belongs to that design.
3. Recompute every affected number once the v1 fixes have landed, and record
   it here. Several v1 fixes change the numbers, including the canonical
   disease organisms.
4. The v2 issues — 2, 5b, 16, 18, 21 and the scoring half of 9 — are not patched
   here. They need a generator change or a decision about what the API should
   mean.
