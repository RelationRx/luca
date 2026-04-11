"""
InfoBandit — rule-based baseline for the LEMONOIDS benchmark.

Strategy:
  Phase 1 — BLOCK every observable gene and record phenotype deltas.
  Phase 2 — UCB-guided BOOST sweep: prioritise high-impact genes with the
             remaining budget, so that the most influential genes get both
             BLOCK and BOOST data before the budget runs out.
  Phase 3 — Logit-space prediction: combine single-gene effects in logit
             space to account for sigmoid saturation in the phenotype readout.
  Phase 4 — Disease diagnosis: score every (gene, LOCK_HI / LOCK_LO) pair
             by how much the complementary fix moves aberrant phenotypes back
             into their healthy ranges; submit the best and test rescue.

Usage:
  python evaluate.py --agent info_bandit.py:run --n 20
  python evaluate.py --agent info_bandit.py:run --disease --difficulty hard
  python evaluate.py --agent info_bandit.py:run --agent-name info-bandit --heuristic --n 20
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPS = 1e-6  # numerical guard for logit / sigmoid


def _logit(p: float) -> float:
    p = max(_EPS, min(1.0 - _EPS, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    # numerically stable
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _logit_combine(baseline_val: float, deltas: list[float]) -> float:
    """
    Combine independent perturbation effects in logit space.

    Each delta is a *linear* shift measured from the same baseline.  Converting
    to logit space makes the combination correct for sigmoid-readout phenotypes:
    effects near the saturation boundaries (0 or 1) are automatically dampened.

    Returns a value in (0, 1).
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
    InfoBandit agent.  Accepts an ExperimentSession and interacts with it
    according to the four-phase strategy described in the module docstring.
    """
    info: dict[str, Any] = session.get_info()
    genes: list[str] = info["gene_names"]
    baseline: dict[str, float] = info["baseline_phenotypes"]
    phenotypes: list[str] = info["observable_phenotypes"]
    is_disease: bool = session.is_disease

    # Reserve 1 experiment for the disease rescue call; predictions are free.
    reserve = 1 if is_disease else 0

    # effect table: (gene, itype) -> {pheno_label: delta}
    effects: dict[tuple[str, str], dict[str, float]] = {}

    def _record(gene: str, itype: str) -> bool:
        """Run one experiment and store the result.  Returns True on success."""
        result = session.run_experiment({gene: {"type": itype}})
        if "error" in result:
            return False
        delta = {
            p: result["phenotypes"].get(p, baseline[p]) - baseline[p]
            for p in phenotypes
        }
        effects[(gene, itype)] = delta
        return True

    def _magnitude(delta: dict[str, float]) -> float:
        return sum(abs(v) for v in delta.values())

    # -----------------------------------------------------------------------
    # Phase 1 — complete BLOCK sweep
    # -----------------------------------------------------------------------
    for gene in genes:
        if session.budget_used >= session.budget - reserve:
            break
        _record(gene, "BLOCK")

    # -----------------------------------------------------------------------
    # Phase 2 — UCB-guided BOOST sweep
    #
    # Prior for each gene's BOOST arm is initialised from its BLOCK magnitude
    # (highly-impactful genes are likely to be informative when BOOSTed too).
    # UCB exploration ensures we don't miss a gene with a lower BLOCK signal
    # that turns out to be highly asymmetric.
    # -----------------------------------------------------------------------
    C = math.sqrt(2.0)  # UCB exploration constant

    # q[gene] = cumulative magnitude from BOOST experiments
    # n[gene] = number of BOOST experiments run for this gene
    # The BLOCK magnitude seeds the prior but is not counted in n (so the
    # exploration bonus is still large enough to force at least one BOOST).
    q: dict[str, float] = {
        gene: _magnitude(effects.get((gene, "BLOCK"), {})) for gene in genes
    }
    n: dict[str, int] = {gene: 0 for gene in genes}
    T = max(len(genes), 1)  # pseudo-count for log; avoids log(0)

    # Candidates: genes that were successfully BLOCKed (we have prior data)
    # and have not yet been BOOSTed.
    candidates = [g for g in genes if (g, "BLOCK") in effects]

    while session.budget_used < session.budget - reserve and candidates:
        # UCB score for each candidate gene's BOOST arm
        best_gene = max(
            candidates,
            key=lambda g: q[g] + C * math.sqrt(math.log(T) / max(n[g], 1)),
        )
        success = _record(best_gene, "BOOST")
        if success:
            boost_mag = _magnitude(effects[(best_gene, "BOOST")])
            q[best_gene] += boost_mag
            n[best_gene] += 1
            T += 1
        candidates.remove(best_gene)

    # -----------------------------------------------------------------------
    # Phase 3 — logit-space prediction
    # -----------------------------------------------------------------------

    def _get_delta(gene: str, itype: str, pheno: str) -> float:
        """
        Return the measured delta for (gene, itype, pheno) with fallbacks for
        arms that were not probed within the available budget.

        Fallback priority:
          BLOCK  not measured → negate BOOST measurement
          BOOST  not measured → negate BLOCK measurement   (sign-flip approx)
          DAMPEN not measured → half of BLOCK effect       (DAMPEN ≤ 0.15 clamp)
        """
        key = (gene, itype)
        if key in effects:
            return effects[key].get(pheno, 0.0)

        if itype == "DAMPEN":
            block_delta = effects.get((gene, "BLOCK"), {}).get(pheno, 0.0)
            return 0.5 * block_delta

        if itype == "BOOST":
            block_delta = effects.get((gene, "BLOCK"), {}).get(pheno, 0.0)
            return -block_delta  # symmetric linear approximation

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

    # -----------------------------------------------------------------------
    # Phase 4 — disease diagnosis and rescue
    # -----------------------------------------------------------------------
    if is_disease:
        aberrant: list[str] = info.get("aberrant_phenotypes", [])
        healthy_ranges: dict[str, list[float]] = info.get(
            "healthy_phenotype_ranges", {}
        )

        best_gene: str = genes[0] if genes else ""
        best_mtype: str = "LOCK_HI"
        best_score: float = float("-inf")

        for gene in genes:
            for mtype, fix_type in (("LOCK_HI", "BLOCK"), ("LOCK_LO", "BOOST")):
                score = 0.0
                for pheno in aberrant:
                    b = baseline[pheno]
                    lo, hi = healthy_ranges.get(pheno, [0.0, 1.0])
                    delta = _get_delta(gene, fix_type, pheno)
                    moved = max(0.0, min(1.0, b + delta))
                    # Positive score = phenotype moved closer to healthy range
                    dist_before = max(0.0, b - hi) + max(0.0, lo - b)
                    dist_after = max(0.0, moved - hi) + max(0.0, lo - moved)
                    score += dist_before - dist_after
                if score > best_score:
                    best_score = score
                    best_gene = gene
                    best_mtype = mtype

        session.submit_malfunction_hypothesis(best_gene, best_mtype)
        rescue_type = "BLOCK" if best_mtype == "LOCK_HI" else "BOOST"
        session.test_rescue({best_gene: {"type": rescue_type}})

    session.submit_hypothesis(
        "InfoBandit: UCB-guided BLOCK+BOOST sweep, logit-space nonlinear prediction, "
        "effect-scored disease diagnosis."
    )
