"""Tests for evaluate.py scoring.

Issue 8. _composite_score built a three-element component list in disease mode
whatever the run asked for:

    diag   = record.get("diagnosis_score") if "diagnose" in active_tasks else None
    rescue = record.get("rescue_fraction") if "rescue" in active_tasks else None
    components = [acc, diag if diag is not None else 0.0,
                  rescue if rescue is not None else 0.0]
    return round(sum(components) / len(components), 4)

Two different situations collapse to the same 0.0:

  1. the task was never requested — it must be excluded from the average;
  2. the task was requested and the model did not attempt it — it must count
     as 0.0, because not attempting is a failed attempt.

The docstring already states that split. The code did not implement it, so a
`--tasks predict rescue` run was divided by three and penalised for a
diagnosis it was never asked to perform.

This is the mechanism CLAUDE.md names: a `.get(..., default)` that turns a
missing measurement into a confident number. The disease branch always writes
"diagnosis_score" and "rescue_fraction" in _make_record, so these tests index
directly and let a missing key raise.
"""
import pytest

import evaluate

FULL = frozenset({"predict", "diagnose", "rescue"})


def _record(acc, diagnosis_score=None, rescue_fraction=None):
    return {
        "avg_accuracy": acc,
        "diagnosis_score": diagnosis_score,
        "rescue_fraction": rescue_fraction,
    }


class TestCompositeScoreDivisor:

    def test_a_subset_run_is_not_penalised_for_a_task_it_was_not_asked_to_do(self):
        # --tasks predict rescue. diagnose was never requested, so the average
        # is over two components: (0.8 + 0.6) / 2.
        #
        # A rescue_fraction of 0.6 under this task set is only reachable from a
        # custom --agent. Through any built-in runner rescue is gated on a
        # locked hypothesis, which needs diagnose active, so rescue_fraction
        # would be None. _composite_score does not know that, and this pins the
        # arithmetic. The reachable CLI case is the diagnose test below.
        score = evaluate._composite_score(
            _record(0.8, rescue_fraction=0.6),
            disease=True,
            active_tasks=frozenset({"predict", "rescue"}),
        )
        assert score == 0.7

    def test_a_predict_only_disease_run_scores_accuracy_alone(self):
        score = evaluate._composite_score(
            _record(0.8),
            disease=True,
            active_tasks=frozenset({"predict"}),
        )
        assert score == 0.8

    def test_a_diagnose_subset_run_averages_two_components(self):
        # (0.8 + 0.5) / 2
        score = evaluate._composite_score(
            _record(0.8, diagnosis_score=0.5),
            disease=True,
            active_tasks=frozenset({"predict", "diagnose"}),
        )
        assert score == 0.65

    def test_a_full_run_still_averages_three_components(self):
        # (0.8 + 0.5 + 0.6) / 3 = 0.6333. This is the published path and it
        # must not move.
        score = evaluate._composite_score(
            _record(0.8, diagnosis_score=0.5, rescue_fraction=0.6),
            disease=True,
            active_tasks=FULL,
        )
        assert score == 0.6333

    def test_an_unattempted_active_task_still_counts_as_zero(self):
        # diagnose WAS requested and the model submitted no hypothesis. That is
        # a failed attempt, not an excluded component: (0.8 + 0.0 + 0.6) / 3.
        score = evaluate._composite_score(
            _record(0.8, diagnosis_score=None, rescue_fraction=0.6),
            disease=True,
            active_tasks=FULL,
        )
        assert score == 0.4667

    def test_the_two_zero_cases_are_told_apart(self):
        # The same record, scored under two different runs. Excluding the
        # component and scoring it 0.0 must not give the same answer.
        record = _record(0.8, diagnosis_score=None, rescue_fraction=0.6)
        not_requested = evaluate._composite_score(
            record, disease=True, active_tasks=frozenset({"predict", "rescue"})
        )
        requested_but_missed = evaluate._composite_score(
            record, disease=True, active_tasks=FULL
        )
        assert not_requested == 0.7
        assert requested_but_missed == 0.4667
        assert not_requested != requested_but_missed

    def test_a_healthy_run_scores_accuracy_alone(self):
        score = evaluate._composite_score(
            _record(0.8), disease=False, active_tasks=FULL
        )
        assert score == 0.8

    def test_a_run_without_predict_has_no_composite_score(self):
        # Pre-existing behaviour that issue 8 did not change: predict is
        # required for a composite score, so --tasks diagnose rescue reports
        # "n/a" even though both requested components were measured. Pinned
        # here so a later change to that guard is deliberate.
        score = evaluate._composite_score(
            _record(0.8), disease=True, active_tasks=frozenset({"diagnose", "rescue"})
        )
        assert score is None

    def test_a_session_with_no_predictions_has_no_composite_score(self):
        score = evaluate._composite_score(
            _record(None, diagnosis_score=0.5, rescue_fraction=0.6),
            disease=True,
            active_tasks=FULL,
        )
        assert score is None

    def test_a_missing_disease_key_raises_rather_than_defaulting(self):
        # _make_record always writes both keys in disease mode. If one is ever
        # absent the score must raise, not quietly read it as 0.0 — that
        # default is the mechanism behind issue 3.
        with pytest.raises(KeyError):
            evaluate._composite_score(
                {"avg_accuracy": 0.8, "rescue_fraction": 0.6},
                disease=True,
                active_tasks=FULL,
            )
