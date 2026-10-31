"""Tests for ExperimentSession."""
import pytest
from luca import generate_organism, generate_disease_organism, ExperimentSession
from luca.experiment import recommended_budget


def test_recommended_budget_scales():
    org = generate_organism(seed=0)
    budget = recommended_budget(org)
    assert budget == len(org.genes) + len(org.signals) + 8


def test_default_budget_uses_recommended():
    org = generate_organism(seed=0)
    session = ExperimentSession(org)
    assert session.budget == recommended_budget(org)


def test_explicit_budget_overrides():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=10)
    assert session.budget == 10


def test_is_disease_healthy():
    org = generate_organism(seed=0)
    session = ExperimentSession(org)
    assert session.is_disease is False


def test_is_disease_disease():
    org = generate_disease_organism(seed=0)
    session = ExperimentSession(org)
    assert session.is_disease is True


def test_get_info_returns_expected_keys():
    org = generate_organism(seed=0)
    session = ExperimentSession(org)
    info = session.get_info()
    assert "gene_names" in info
    assert "signals" in info
    assert "observable_phenotypes" in info
    assert "baseline_phenotypes" in info
    assert "budget_remaining" in info
    assert "budget_total" in info


def test_get_info_disease_extra_keys():
    org = generate_disease_organism(seed=0)
    session = ExperimentSession(org)
    info = session.get_info()
    assert "aberrant_phenotypes" in info
    assert "healthy_phenotype_ranges" in info
    assert len(info["aberrant_phenotypes"]) >= 1


def test_run_experiment_costs_budget():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    first_gene = [g for g in session.get_info()["gene_names"]][0]
    session.run_experiment({first_gene: {"type": "BLOCK"}})
    assert session.budget_used == 1


def test_run_experiment_unknown_target():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    result = session.run_experiment({"NOTEXIST": {"type": "BLOCK"}})
    assert "error" in result


def test_run_experiment_budget_exhausted():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=1)
    gene = session.get_info()["gene_names"][0]
    session.run_experiment({gene: {"type": "BLOCK"}})
    result = session.run_experiment({gene: {"type": "BOOST"}})
    assert "error" in result


def test_submit_prediction_scores_correctly():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    task = session.get_next_prediction_task()
    task_id = task["task_id"]
    phenotype_labels = session.get_info()["observable_phenotypes"]
    perfect = {label: 0.5 for label in phenotype_labels}
    result = session.submit_prediction(task_id, perfect)
    assert "mse" in result
    assert "accuracy" in result
    assert 0.0 <= result["accuracy"] <= 1.0


def test_prediction_tasks_sequential():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=10)
    task1 = session.get_next_prediction_task()
    assert not task1.get("done")
    # Second call before submitting returns same task
    task1b = session.get_next_prediction_task()
    assert task1["task_id"] == task1b["task_id"]


def test_disease_rescue_requires_hypothesis_first():
    org = generate_disease_organism(seed=0)
    session = ExperimentSession(org, budget=10)
    gene = session.get_info()["gene_names"][0]
    result = session.test_rescue({gene: {"type": "BLOCK"}})
    assert "error" in result


def test_disease_hypothesis_locks_on_first_call():
    org = generate_disease_organism(seed=0)
    session = ExperimentSession(org, budget=10)
    hyp1 = session.submit_malfunction_hypothesis("G001", "LOCK_HI")
    assert hyp1.get("stored") is True
    hyp2 = session.submit_malfunction_hypothesis("G002", "LOCK_LO")
    assert "error" in hyp2


def test_disease_rescue_available_after_hypothesis():
    org = generate_disease_organism(seed=0)
    session = ExperimentSession(org, budget=10)
    session.submit_malfunction_hypothesis("G001", "LOCK_HI")
    gene = session.get_info()["gene_names"][0]
    result = session.test_rescue({gene: {"type": "BLOCK"}})
    assert "restored_fraction" in result
    assert "mse_vs_healthy" in result


def test_get_summary_keys():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    summary = session.get_summary()
    assert "organism_id" in summary
    assert "budget_total" in summary
    assert "budget_used" in summary
    assert "prediction_results" in summary
    assert "avg_mse" in summary


def test_resolve_interventions_error_on_latent():
    """Latent genes should not be targetable."""
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    if org.latent_genes:
        from luca.schema import Gene
        latent_id = org.latent_genes[0]
        latent_name = next(g.name for g in org.genes if g.id == latent_id)
        result = session._resolve_interventions({latent_name: {"type": "BLOCK"}})
        assert isinstance(result, dict) and "error" in result


def test_prediction_tasks_non_trivial():
    """Every prediction task must shift at least one phenotype by >= 0.1 from baseline."""
    for seed in range(5):
        org = generate_organism(seed=seed, n_genes=15, n_modules=4)
        session = ExperimentSession(org, seed=seed)
        baseline = session._compute_baseline_phenotypes()
        for tid, task in session._tasks.items():
            max_shift = max(
                abs(task.ground_truth[lbl] - baseline[lbl]) for lbl in baseline
            )
            assert max_shift >= 0.1, (
                f"seed={seed} {tid}: max phenotype shift {max_shift:.3f} < 0.1 threshold"
            )


def test_n_diagnosis_alternatives_in_summary():
    """n_diagnosis_alternatives must appear in disease session summary."""
    org = generate_disease_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    summary = session.get_summary()
    assert "n_diagnosis_alternatives" in summary
    assert isinstance(summary["n_diagnosis_alternatives"], int)


def test_n_prediction_tasks_configurable():
    """n_prediction_tasks parameter should control the number of tasks generated."""
    org = generate_organism(seed=0)
    s0 = ExperimentSession(org, n_prediction_tasks=0)
    assert len(s0._tasks) == 0
    s4 = ExperimentSession(org, n_prediction_tasks=4)
    assert len(s4._tasks) == 4


def test_active_tasks_predict_excluded():
    """When predict is excluded no tasks are generated and get_next_prediction_task returns done."""
    org = generate_organism(seed=0)
    session = ExperimentSession(org, active_tasks=frozenset({"diagnose", "rescue"}))
    assert len(session._tasks) == 0
    result = session.get_next_prediction_task()
    assert result.get("done") is True


def test_active_tasks_in_summary():
    """active_tasks should appear in get_summary()."""
    org = generate_organism(seed=0)
    tasks = frozenset({"predict"})
    session = ExperimentSession(org, active_tasks=tasks)
    summary = session.get_summary()
    assert "active_tasks" in summary
    assert set(summary["active_tasks"]) == tasks


def test_disease_end_to_end():
    """Full disease session: diagnose → rescue → predict → summarise."""
    org = generate_disease_organism(seed=3)
    session = ExperimentSession(org, budget=30, seed=0)

    info = session.get_info()
    assert info["aberrant_phenotypes"]

    # Run a few experiments
    gene = info["gene_names"][0]
    session.run_experiment({gene: {"type": "BLOCK"}})

    # Submit (likely wrong) malfunction hypothesis
    result = session.submit_malfunction_hypothesis(gene, "LOCK_HI")
    assert result.get("stored") is True
    assert session._hypothesis_locked

    # Rescue attempt
    rescue = session.test_rescue({gene: {"type": "BLOCK"}})
    assert "restored_fraction" in rescue

    # Prediction tasks
    phenotype_labels = info["observable_phenotypes"]
    while True:
        task = session.get_next_prediction_task()
        if task.get("done"):
            break
        prediction = {lbl: 0.5 for lbl in phenotype_labels}
        session.submit_prediction(task["task_id"], prediction)

    session.submit_hypothesis("Test hypothesis.")
    summary = session.get_summary()
    assert summary["malfunction_hypothesis"] is not None
    assert len(summary["rescue_results"]) >= 1
    assert summary["avg_accuracy"] is not None


def test_malfunction_hypothesis_scoring():
    """Scoring rubric: 1.0 exact, 0.5 right target wrong type, 0.0 wrong."""
    org = generate_disease_organism(seed=1)
    m = org.malfunctions[0]

    # Exact match
    s_exact = ExperimentSession(org, budget=5)
    s_exact.submit_malfunction_hypothesis(m.target_name, m.type)
    assert s_exact._malfunction_guess["score"] == 1.0

    # Right target, wrong type
    wrong_type = "LOCK_LO" if m.type == "LOCK_HI" else "LOCK_HI"
    s_partial = ExperimentSession(org, budget=5)
    s_partial.submit_malfunction_hypothesis(m.target_name, wrong_type)
    assert s_partial._malfunction_guess["score"] == 0.5

    # Wrong target entirely
    other_gene = next(g.name for g in org.genes if g.name != m.target_name)
    s_wrong = ExperimentSession(org, budget=5)
    s_wrong.submit_malfunction_hypothesis(other_gene, m.type)
    assert s_wrong._malfunction_guess["score"] == 0.0


# ----------------------------------------------------------------------
# PERSIST malfunctions must remain active during in-session simulations.
# Regression test for the bug where the chronic signal override was baked
# into the displayed disease baseline but dropped from run_experiment /
# test_rescue / prediction-task simulations, so PERSIST organisms silently
# relaxed to healthy no matter what the agent did.
# ----------------------------------------------------------------------

def _persist_disease_organism():
    """First seed whose disease organism carries a PERSIST malfunction."""
    for seed in range(40):
        org = generate_disease_organism(difficulty="medium", seed=seed)
        if any(m.type == "PERSIST" for m in org.malfunctions):
            return org
    pytest.skip("no PERSIST organism found in seed range")


def _aberrant(org, phenos):
    return [
        lbl for lbl, v in phenos.items()
        if not (org.healthy_phenotype_ranges[lbl][0] <= v <= org.healthy_phenotype_ranges[lbl][1])
    ]


def test_persist_malfunction_active_during_experiments():
    org = _persist_disease_organism()
    session = ExperimentSession(org, seed=0)

    baseline = session.get_info()["baseline_phenotypes"]
    assert _aberrant(org, baseline), "disease baseline should be aberrant"

    # A do-nothing experiment must NOT cure the organism: the persistent
    # signal is part of the disease, not just of the displayed baseline.
    result = session.run_experiment({})
    assert _aberrant(org, result["phenotypes"]), (
        "PERSIST organism relaxed to healthy under a null experiment — "
        "the chronic signal override is not being applied at runtime"
    )


def test_persist_malfunction_active_during_rescue():
    org = _persist_disease_organism()
    session = ExperimentSession(org, seed=0)
    m = org.malfunctions[0]
    session.submit_malfunction_hypothesis(m.target_name, m.type)

    # A null rescue must not restore all aberrant phenotypes by itself.
    rescue = session.test_rescue({})
    assert rescue["restored_fraction"] < 1.0, (
        "null rescue reported full restoration — persistent signal missing "
        "from the rescue simulation"
    )


# ----------------------------------------------------------------------
# LOCK_HI / LOCK_LO malfunctions must remain active during in-session
# simulations, and must be genuinely rescuable by the documented
# corrective intervention (BLOCK for LOCK_HI, BOOST for LOCK_LO).
#
# Regression test for seam-bug audit item 2 (2026-08-20,
# BUG_AUDIT_JOBSPEC.md): PERSIST got dedicated tests after its runtime
# bug (PR #127); LOCK_HI/LOCK_LO never got the equivalent check. They use
# a different mechanism — the malfunction's bias is baked into
# org.dynamics.rule at generation time (generation.py), not re-injected
# per-call like PERSIST's signal override — so no equivalent runtime
# guard exists in ExperimentSession, nor is one needed: simulate_sigmoid
# always reads the mutated rule. Verified clean by reading generation.py;
# this test locks that behaviour in rather than leaving it unverified.
# ----------------------------------------------------------------------

def _lock_organism(mtype, margin=0.05):
    """First seed whose disease organism carries a *robustly* aberrant
    malfunction of mtype: the deterministic (noise=False) baseline must
    clear the healthy range by more than `margin`, so run_experiment's
    per-call simulation noise (noise_sigma=0.01, phenotype noise 2x that)
    can't flip aberrant/healthy by chance and produce a false pass/fail.
    Found by direct testing: the first LOCK_HI organism (seed 8) had only
    a 0.008 margin and flipped healthy under noise on ~40% of draws — not
    a runtime-application bug, just too close to the boundary to test
    against reliably.
    """
    for seed in range(60):
        org = generate_disease_organism(difficulty="medium", seed=seed)
        if not any(m.type == mtype for m in org.malfunctions):
            continue
        baseline = ExperimentSession(org, seed=0)._compute_baseline_phenotypes()
        for lbl, v in baseline.items():
            lo, hi = org.healthy_phenotype_ranges[lbl]
            if v < lo - margin or v > hi + margin:
                return org
    pytest.skip(f"no robustly-aberrant {mtype} organism found in seed range")


def test_lock_hi_malfunction_active_during_experiments():
    org = _lock_organism("LOCK_HI")
    session = ExperimentSession(org, seed=0)

    baseline = session.get_info()["baseline_phenotypes"]
    assert _aberrant(org, baseline), "disease baseline should be aberrant"

    # A do-nothing experiment must NOT cure the organism: the locked-high
    # gene's bias is baked into the organism's dynamics rule, not
    # something a null intervention can undo.
    result = session.run_experiment({})
    assert _aberrant(org, result["phenotypes"]), (
        "LOCK_HI organism relaxed to healthy under a null experiment — "
        "the locked-high gene bias is not being applied at runtime"
    )


def test_lock_hi_malfunction_rescuable_by_block():
    org = _lock_organism("LOCK_HI")
    session = ExperimentSession(org, seed=0)
    m = next(mm for mm in org.malfunctions if mm.type == "LOCK_HI")
    session.submit_malfunction_hypothesis(m.target_name, m.type)

    # A null rescue must not restore all aberrant phenotypes by itself.
    null_rescue = session.test_rescue({})
    assert null_rescue["restored_fraction"] < 1.0, (
        "null rescue reported full restoration for a LOCK_HI organism"
    )

    # BLOCKing the locked-high gene is the documented corrective action
    # (generation.py's own generation-time probe verifies this before
    # selecting a malfunction as "effective") — it must actually help.
    blocked_rescue = session.test_rescue({m.target_name: {"type": "BLOCK"}})
    assert blocked_rescue["restored_fraction"] > null_rescue["restored_fraction"], (
        "BLOCKing the locked-high gene did not improve rescue over doing nothing"
    )


def test_lock_lo_malfunction_active_during_experiments():
    org = _lock_organism("LOCK_LO")
    session = ExperimentSession(org, seed=0)

    baseline = session.get_info()["baseline_phenotypes"]
    assert _aberrant(org, baseline), "disease baseline should be aberrant"

    result = session.run_experiment({})
    assert _aberrant(org, result["phenotypes"]), (
        "LOCK_LO organism relaxed to healthy under a null experiment — "
        "the locked-low gene bias is not being applied at runtime"
    )


def test_lock_lo_malfunction_rescuable_by_boost():
    org = _lock_organism("LOCK_LO")
    session = ExperimentSession(org, seed=0)
    m = next(mm for mm in org.malfunctions if mm.type == "LOCK_LO")
    session.submit_malfunction_hypothesis(m.target_name, m.type)

    null_rescue = session.test_rescue({})
    assert null_rescue["restored_fraction"] < 1.0, (
        "null rescue reported full restoration for a LOCK_LO organism"
    )

    boosted_rescue = session.test_rescue({m.target_name: {"type": "BOOST"}})
    assert boosted_rescue["restored_fraction"] > null_rescue["restored_fraction"], (
        "BOOSTing the locked-low gene did not improve rescue over doing nothing"
    )


# ---------------------------------------------------------------------------
# Rescue scoring: only the aberrant phenotypes count
# ---------------------------------------------------------------------------

def _locked_disease_session(seed: int = 1, **kwargs):
    """A disease session with the hypothesis submitted, so rescue is unlocked."""
    org = generate_disease_organism(seed=seed, **kwargs)
    session = ExperimentSession(org)
    session.submit_malfunction_hypothesis(org.genes[0].name, "LOCK_HI")
    return org, session


def test_empty_intervention_scores_zero():
    """
    An intervention that changes nothing must score 0.0.

    Regression test for the scoring bug a reviewer found: restored_fraction
    used to count every phenotype inside its healthy range, so an empty
    intervention on an organism with 1 of 3 phenotypes aberrant scored
    2/3 = 0.6667 while fixing nothing.
    """
    org, session = _locked_disease_session(seed=1)
    result = session.test_rescue({})
    assert result["restored_fraction"] == 0.0
    # The old quantity is still reported, under a name that says what it is.
    assert result["all_phenotypes_in_range_fraction"] > 0.0


def test_rescue_counts_only_aberrant_phenotypes():
    """restored_fraction is scored against the aberrant set, not all phenotypes."""
    org, session = _locked_disease_session(seed=1)
    result = session.test_rescue({})
    aberrant = result["aberrant_phenotypes"]
    assert 0 < len(aberrant) < len(org.healthy_phenotype_ranges)
    assert result["n_aberrant"] == len(aberrant)
    # Every aberrant phenotype is still out of range after doing nothing.
    assert all(not result["phenotype_in_healthy_range"][p] for p in aberrant)


def test_rescue_reports_collateral_damage_separately():
    """Breaking a healthy phenotype is counted, not folded into the score."""
    org, session = _locked_disease_session(seed=1)
    result = session.test_rescue({})
    assert result["healthy_phenotypes_broken"] == 0
    assert "healthy_phenotypes_broken" in result


def test_aberrant_set_agrees_across_api():
    """get_info, get_summary and test_rescue must report the same aberrant set."""
    org, session = _locked_disease_session(seed=1)
    from_info = set(session.get_info()["aberrant_phenotypes"])
    from_rescue = set(session.test_rescue({})["aberrant_phenotypes"])
    from_summary = set(session.get_summary()["aberrant_phenotypes"])
    assert from_info == from_rescue == from_summary
