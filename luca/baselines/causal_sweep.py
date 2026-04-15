"""
CausalSweep — improved rule-based baseline for the LUCA benchmark.

Strategy:
  Phase 1 — BLOCK every observable gene and record phenotype deltas.
  Phase 2 — Multi-phenotype-priority BOOST sweep: prioritise genes that affect
             the most phenotypes (these are most likely to appear in prediction
             tasks, which target shared-readout gene pairs).
  Phase 3 — Logit-space prediction: combine single-gene effects in logit space
             to account for sigmoid saturation in the phenotype readout.
  Phase 4 — Disease diagnosis and rescue (decoupled: best rescue is selected
             independently from diagnosis hypothesis).

Key improvement over InfoBandit: BOOST allocation uses multi-phenotype-priority
ordering instead of UCB, ensuring measured BOOST data for task-relevant genes
rather than relying on the noisy symmetric fallback (BOOST = -BLOCK).

Usage:
  python evaluate.py --agent luca/baselines/causal_sweep.py:run --n 20
  python evaluate.py --agent luca/baselines/causal_sweep.py:run --disease --difficulty hard
  python evaluate.py --agent luca/baselines/causal_sweep.py:run --agent-name causal-sweep --heuristic --n 20
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPS = 1e-6


def _logit(p: float) -> float:
    p = max(_EPS, min(1.0 - _EPS, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _logit_combine(baseline_val: float, deltas: list[float]) -> float:
    """
    Combine independent perturbation effects in logit space.

    Each delta is a linear shift measured from the same baseline.  Converting
    to logit space makes the combination correct for sigmoid-readout phenotypes:
    effects near the saturation boundaries (0 or 1) are automatically dampened.
    """
    b = max(_EPS, min(1.0 - _EPS, baseline_val))
    logit_b = _logit(b)
    logit_total = logit_b
    for delta in deltas:
        perturbed = max(_EPS, min(1.0 - _EPS, b + delta))
        logit_total += _logit(perturbed) - logit_b
    return _sigmoid(logit_total)


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------


def run(session) -> None:
    """
    CausalSweep agent.  Accepts an ExperimentSession and interacts with it
    according to the four-phase strategy described in the module docstring.
    """
    info: dict[str, Any] = session.get_info()
    genes: list[str] = info["gene_names"]
    baseline: dict[str, float] = info["baseline_phenotypes"]
    phenotypes: list[str] = info["observable_phenotypes"]
    is_disease: bool = session.is_disease

    reserve = 1 if is_disease else 0

    # effect table: (gene, itype) -> {pheno_label: delta}
    effects: dict[tuple[str, str], dict[str, float]] = {}

    def _record(gene: str, itype: str) -> bool:
        result = session.run_experiment({gene: {"type": itype}})
        if "error" in result:
            return False
        delta = {
            p: result["phenotypes"].get(p, baseline[p]) - baseline[p]
            for p in phenotypes
        }
        effects[(gene, itype)] = delta
        return True

    # -------------------------------------------------------------------
    # Phase 1 — complete BLOCK sweep
    # -------------------------------------------------------------------
    for gene in genes:
        if session.budget_used >= session.budget - reserve:
            break
        _record(gene, "BLOCK")

    # -------------------------------------------------------------------
    # Phase 2 — multi-phenotype-priority BOOST sweep
    #
    # Genes affecting more phenotypes are more likely to appear in
    # prediction tasks (which target shared-readout gene pairs).
    # Prioritise these for BOOST so we have measured data instead of
    # relying on the symmetric BOOST = -BLOCK fallback.
    # -------------------------------------------------------------------
    EFFECT_THRESHOLD = 0.02

    candidates = [g for g in genes if (g, "BLOCK") in effects]

    def _boost_priority(gene: str) -> tuple[int, float]:
        block_delta = effects.get((gene, "BLOCK"), {})
        n_affected = sum(
            1 for p in phenotypes if abs(block_delta.get(p, 0.0)) > EFFECT_THRESHOLD
        )
        total_magnitude = sum(abs(v) for v in block_delta.values())
        return (-n_affected, -total_magnitude)

    candidates.sort(key=_boost_priority)

    for gene in candidates:
        if session.budget_used >= session.budget - reserve:
            break
        _record(gene, "BOOST")

    # -------------------------------------------------------------------
    # Phase 3 — logit-space prediction
    # -------------------------------------------------------------------

    def _get_delta(gene: str, itype: str, pheno: str) -> float:
        """
        Return the measured delta for (gene, itype, pheno) with fallbacks.

        Fallback priority:
          BLOCK  not measured -> negate BOOST measurement
          BOOST  not measured -> negate BLOCK measurement
          DAMPEN not measured -> 0.6 * BLOCK effect
        """
        key = (gene, itype)
        if key in effects:
            return effects[key].get(pheno, 0.0)

        if itype == "DAMPEN":
            block_delta = effects.get((gene, "BLOCK"), {}).get(pheno, 0.0)
            return 0.6 * block_delta

        if itype == "BOOST":
            block_delta = effects.get((gene, "BLOCK"), {}).get(pheno, 0.0)
            return -block_delta

        if itype == "BLOCK":
            boost_delta = effects.get((gene, "BOOST"), {}).get(pheno, 0.0)
            return -boost_delta

        return 0.0

    while True:
        task = session.get_next_prediction_task()
        if task.get("done"):
            break

        prediction: dict[str, float] = {}
        for pheno in task["phenotype_labels"]:
            b = baseline[pheno]
            deltas = [
                _get_delta(gene, iv.get("type", "BLOCK"), pheno)
                for gene, iv in task["interventions"].items()
            ]
            prediction[pheno] = _logit_combine(b, deltas)

        session.submit_prediction(task["task_id"], prediction)

    # -------------------------------------------------------------------
    # Phase 4 — disease diagnosis and rescue (decoupled)
    # -------------------------------------------------------------------
    if is_disease:
        aberrant: list[str] = info.get("aberrant_phenotypes", [])
        healthy_ranges: dict[str, list[float]] = info.get(
            "healthy_phenotype_ranges", {}
        )

        # Diagnosis: find the (gene, malfunction_type) pair whose corrective
        # intervention best explains the aberrant phenotype pattern.
        best_diag_gene: str = genes[0] if genes else ""
        best_diag_mtype: str = "LOCK_HI"
        best_diag_score: float = float("-inf")

        for gene in genes:
            for mtype, fix_type in (("LOCK_HI", "BLOCK"), ("LOCK_LO", "BOOST")):
                score = 0.0
                for pheno in aberrant:
                    b = baseline[pheno]
                    lo, hi = healthy_ranges.get(pheno, [0.0, 1.0])
                    delta = _get_delta(gene, fix_type, pheno)
                    moved = max(0.0, min(1.0, b + delta))
                    dist_before = max(0.0, b - hi) + max(0.0, lo - b)
                    dist_after = max(0.0, moved - hi) + max(0.0, lo - moved)
                    score += dist_before - dist_after
                if score > best_diag_score:
                    best_diag_score = score
                    best_diag_gene = gene
                    best_diag_mtype = mtype

        session.submit_malfunction_hypothesis(best_diag_gene, best_diag_mtype)

        # Rescue: independently pick the single-gene intervention that best
        # restores aberrant phenotypes (may differ from diagnosis gene).
        best_rescue_gene: str = best_diag_gene
        best_rescue_type: str = "BLOCK" if best_diag_mtype == "LOCK_HI" else "BOOST"
        best_rescue_score: float = float("-inf")

        for gene in genes:
            for fix_type in ("BLOCK", "BOOST"):
                score = 0.0
                for pheno in aberrant:
                    b = baseline[pheno]
                    lo, hi = healthy_ranges.get(pheno, [0.0, 1.0])
                    delta = _get_delta(gene, fix_type, pheno)
                    moved = max(0.0, min(1.0, b + delta))
                    dist_before = max(0.0, b - hi) + max(0.0, lo - b)
                    dist_after = max(0.0, moved - hi) + max(0.0, lo - moved)
                    score += dist_before - dist_after
                if score > best_rescue_score:
                    best_rescue_score = score
                    best_rescue_gene = gene
                    best_rescue_type = fix_type

        session.test_rescue({best_rescue_gene: {"type": best_rescue_type}})

    session.submit_hypothesis(
        "CausalSweep: multi-phenotype-priority BOOST sweep, logit-space nonlinear "
        "prediction, decoupled disease diagnosis and rescue."
    )
