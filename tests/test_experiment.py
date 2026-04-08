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
