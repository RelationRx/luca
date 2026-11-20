"""Heuristic baseline: systematic BLOCK sweep + additive prediction."""
from __future__ import annotations

from typing import Any

# How each intervention type moves a phenotype, as a multiple of the measured
# BLOCK delta (phenotype after BLOCK, minus baseline).
#
#   BLOCK  clamps the gene to 0.0, which is the state that was measured, so
#          the measured delta is the prediction.
#   DAMPEN clamps the gene to at most 0.15 — nearly the same state as BLOCK —
#          so it moves the phenotype the same way.
#   BOOST  clamps the gene to 1.0, the opposite extreme, so the response is
#          taken as the opposite of the BLOCK delta.
#
# The BOOST magnitude is an estimate, not a calibration. Agents never see gene
# states, so the baseline activity a BOOST moves away from is unknown. This
# baseline exists to show what a non-adaptive additive rule achieves, not to
# be the strongest possible one.
_DELTA_MULTIPLIER = {"BLOCK": 1.0, "DAMPEN": 1.0, "BOOST": -1.0}


def _additive_prediction(
    baseline: dict[str, float],
    effects: dict[str, dict[str, float]],
    interventions: dict[str, Any],
    phenotype_labels: list[str],
) -> dict[str, float]:
    """
    Predict a combined intervention by adding each gene's measured BLOCK delta,
    scaled for the intervention type actually requested.

    Genes with no measurement contribute nothing. Results are clipped to [0, 1].
    """
    prediction: dict[str, float] = {}
    for label in phenotype_labels:
        value = baseline[label]
        for gene, intervention in interventions.items():
            if gene not in effects:
                continue
            itype = intervention.get("type") if isinstance(intervention, dict) else intervention
            multiplier = _DELTA_MULTIPLIER.get(str(itype).upper(), 1.0)
            value += multiplier * effects[gene].get(label, 0.0)
        prediction[label] = max(0.0, min(1.0, value))
    return prediction


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
            prediction = _additive_prediction(
                baseline, effects, task["interventions"], phenotype_labels
            )
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
