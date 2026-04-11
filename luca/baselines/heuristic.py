"""Heuristic baseline: systematic BLOCK sweep + additive prediction."""
from __future__ import annotations

from typing import Any


def run_heuristic(session, active_tasks: frozenset[str] | None = None) -> dict[str, Any]:
    """
    Systematic heuristic agent: BLOCK all observable genes one by one,
    then make additive predictions. No API calls required.
    """
    if active_tasks is None:
        active_tasks = frozenset({"predict", "diagnose", "rescue"})

    info = session.get_info()
    gene_names = info["gene_names"]
    baseline = info["baseline_phenotypes"]
    phenotype_labels = info["observable_phenotypes"]

    # Phase 1: BLOCK each gene and record phenotype shifts
    effects: dict[str, dict[str, float]] = {}
    for gene in gene_names:
        if session.budget_used >= session.budget - 2:
            break
        result = session.run_experiment({gene: {"type": "BLOCK"}})
        if "error" not in result:
            effects[gene] = {
                label: result["phenotypes"].get(label, baseline[label]) - baseline[label]
                for label in phenotype_labels
            }

    # Phase 2: submit predictions using additive model
    if "predict" in active_tasks:
        while True:
            task = session.get_next_prediction_task()
            if task.get("done"):
                break
            prediction: dict[str, float] = {}
            for label in phenotype_labels:
                pred = baseline[label]
                for gene, iv in task["interventions"].items():
                    if gene in effects:
                        sign = -1.0 if iv.get("type") == "BLOCK" else 1.0
                        pred += sign * effects[gene].get(label, 0.0)
                prediction[label] = max(0.0, min(1.0, pred))
            session.submit_prediction(task["task_id"], prediction)

    # Disease mode: naive hypothesis + rescue attempt
    if session.is_disease:
        disease_info = session.get_info()
        aberrant = disease_info.get("aberrant_phenotypes", [])
        # Pick gene with largest effect on aberrant phenotypes as hypothesis
        best_gene = gene_names[0]
        best_score = -1.0
        for gene, eff in effects.items():
            score = sum(abs(eff.get(label, 0.0)) for label in aberrant)
            if score > best_score:
                best_score = score
                best_gene = gene
        if "diagnose" in active_tasks:
            session.submit_malfunction_hypothesis(best_gene, "LOCK_HI")
        if "rescue" in active_tasks and session._hypothesis_locked:
            session.test_rescue({best_gene: {"type": "BLOCK"}})

    session.submit_hypothesis("Heuristic systematic sweep — no causal model.")
    return session.get_summary()
