"""
Tests for the additivity verifier in verify_organisms.py.

Issue 3 of the November 2026 review. It has two halves, both in
check_additivity, and fixing either alone leaves the verifier wrong:

  1. It looked up ``gene.id`` (``g_019``) in a dict keyed by ``gene.name``
     (``G019``). The overlap is empty, so every measured effect fell back to
     0.0 and the additive prediction was just the unperturbed baseline. The
     verifier therefore reported every task at every tier as non-additive,
     and the published additive rate of 0.00 is an artefact of that.
  2. It multiplied BLOCK effects by -1.0, although
     _noiseless_single_gene_effects already measures a BLOCK delta, and it
     measured only BLOCK even when a task asked for BOOST or DAMPEN.

The true rates, measured independently during the review, are
easy 40/40, medium 40/40, hard 18/40 over seeds 0-19. See KNOWN_ISSUES.md.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from luca import ExperimentSession, generate_organism
from luca.dynamics import compute_phenotypes, simulate_sigmoid

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_verify_organisms():
    spec = importlib.util.spec_from_file_location(
        "verify_organisms_under_test", REPO_ROOT / "verify_organisms.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vo = _load_verify_organisms()


# ---------------------------------------------------------------------------
# A second, independent path to the same quantity.
#
# This repeats none of verify_organisms.py's code. It is the recipe the
# November 2026 review used: measure each of the task's own interventions on
# its own, add the deltas to the unperturbed baseline, clip once, and compare
# with ground truth.
# ---------------------------------------------------------------------------

THRESHOLD = 0.10


def _noiseless(org, interventions):
    result = simulate_sigmoid(
        org, interventions=interventions, active_signals={},
        rng=np.random.default_rng(0),
    )
    return compute_phenotypes(
        org, result["final_state"], rng=np.random.default_rng(0), noise=False
    )


def _independent_task_errors(org, task):
    """Max |additive prediction - ground truth| over the phenotypes of one task."""
    baseline = _noiseless(org, {})
    additive = dict(baseline)
    for gene_id, intervention in task.interventions.items():
        single = _noiseless(org, {gene_id: intervention})
        for label in baseline:
            additive[label] += single[label] - baseline[label]
    return max(
        abs(min(1.0, max(0.0, additive[label])) - task.ground_truth[label])
        for label in task.ground_truth
    )


def _independent_rate(tier, n_seeds=20):
    solved = total = 0
    for seed in range(n_seeds):
        org = generate_organism(seed=seed, difficulty=tier)
        session = ExperimentSession(org, budget=31, seed=seed)
        for task in session._tasks.values():
            total += 1
            if _independent_task_errors(org, task) <= THRESHOLD:
                solved += 1
    return solved, total


def _run_check(seed, tier):
    org = generate_organism(seed=seed, difficulty=tier)
    session = ExperimentSession(org, budget=31, seed=seed)
    baseline = vo._noiseless_phenotypes(org, {})
    effects = vo._noiseless_single_gene_effects(org, baseline, list(baseline))
    return session, org, vo.check_additivity(session, effects, baseline), effects, baseline


# ---------------------------------------------------------------------------
# Issue 3 — the key mismatch
# ---------------------------------------------------------------------------

def test_measured_effects_are_keyed_by_the_id_the_tasks_use():
    session, org, _result, effects, _baseline = _run_check(0, "medium")
    task = next(iter(session._tasks.values()))
    assert set(task.interventions) & set(effects), (
        f"no overlap: task keys {sorted(task.interventions)}, "
        f"effect keys {sorted(effects)[:3]}..."
    )


def test_removing_the_measured_effects_changes_the_verdict():
    """The verifier used to give the same answer with an empty effects dict."""
    session, _org, with_effects, _effects, baseline = _run_check(0, "medium")
    without = vo.check_additivity(session, {}, baseline)
    assert with_effects["mean_max_error"] != without["mean_max_error"]


# ---------------------------------------------------------------------------
# Issue 3, second half — the sign, and the resulting published rates
# ---------------------------------------------------------------------------

def test_reported_error_matches_an_independent_computation():
    """One absolute anchor: the verifier's own number, re-derived another way."""
    session, org, result, _effects, _baseline = _run_check(0, "medium")
    by_task = {t["task_id"]: t["max_additive_error"] for t in result["tasks"]}
    for task_id, task in session._tasks.items():
        expected = round(_independent_task_errors(org, task), 4)
        assert by_task[task_id] == pytest.approx(expected, abs=5e-4), task_id


@pytest.mark.parametrize("tier,expected_solved,expected_total", [
    ("easy", 40, 40),
    ("medium", 40, 40),
    ("hard", 18, 40),
])
def test_additive_rate_reproduces_the_november_2026_measurement(
    tier, expected_solved, expected_total
):
    solved = total = 0
    for seed in range(20):
        _session, _org, result, _effects, _baseline = _run_check(seed, tier)
        solved += result["n_additively_solvable"]
        total += result["n_tasks"]
    assert (solved, total) == (expected_solved, expected_total)


def test_the_independent_path_agrees_with_the_published_rates():
    """Guards the anchor itself: if this drifts, the rates above are stale."""
    assert _independent_rate("medium") == (40, 40)
    assert _independent_rate("hard") == (18, 40)
