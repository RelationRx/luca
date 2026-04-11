"""Random baseline: no experiments, predict 0.5 everywhere."""
from __future__ import annotations

from typing import Any


def run_random(session, active_tasks: frozenset[str] | None = None, seed: int = 0) -> dict[str, Any]:
    """
    Random baseline: runs no experiments, predicts 0.5 for every phenotype.

    0.5 is the only sensible no-information prediction — all baseline phenotypes
    are exactly 0.5 by construction, so this is the prior. MSE against the true
    intervention outcome gives the floor score without any causal reasoning.

    In disease mode: submits a random gene / random malfunction type hypothesis
    and a random rescue intervention.
    """
    import random as _random
    rng = _random.Random(seed)

    if active_tasks is None:
        active_tasks = frozenset({"predict", "diagnose", "rescue"})

    info = session.get_info()
    gene_names = info["gene_names"]
    phenotype_labels = info["observable_phenotypes"]

    # Predict 0.5 for every phenotype on every task — no experiments run
    if "predict" in active_tasks:
        while True:
            task = session.get_next_prediction_task()
            if task.get("done"):
                break
            prediction = {label: 0.5 for label in phenotype_labels}
            session.submit_prediction(task["task_id"], prediction)

    # Disease mode: random hypothesis + random rescue
    if session.is_disease:
        malfunction_types = ["LOCK_HI", "LOCK_LO", "PERSIST"]
        if "diagnose" in active_tasks:
            session.submit_malfunction_hypothesis(
                rng.choice(gene_names), rng.choice(malfunction_types)
            )
        if "rescue" in active_tasks and session._hypothesis_locked:
            rescue_gene = rng.choice(gene_names)
            rescue_type = rng.choice(["BLOCK", "BOOST", "DAMPEN"])
            session.test_rescue({rescue_gene: {"type": rescue_type}})

    session.submit_hypothesis("Random baseline — no experiments, predict 0.5 everywhere.")
    return session.get_summary()
