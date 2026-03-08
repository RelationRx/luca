"""ExperimentSession — budget-limited perturbation interface."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .dynamics import simulate_sigmoid
from .schema import Organism


def recommended_budget(organism: Organism, overhead: int = 8) -> int:
    """
    Return a budget that scales linearly with organism complexity.

    Formula: n_genes + n_signals + overhead

    The overhead covers follow-up experiments (BOOST/DAMPEN on candidates),
    rescue tests, and prediction tasks. Default overhead=8 is calibrated
    for a disease session; reduce to 5 for healthy-only sessions.

    Examples:
        15 genes + 3 signals → 26
        20 genes + 3 signals → 31
        25 genes + 5 signals → 38
    """
    return len(organism.genes) + len(organism.signals) + overhead


@dataclass
class PredictionTask:
    id: str
    interventions: dict[str, Any]   # {gene_id → {"type": str}}
    ground_truth: dict[str, float]  # {phenotype_label → value}
    signal_overrides: dict[str, float] = field(default_factory=dict)


@dataclass
class PredictionResult:
    task_id: str
    prediction: dict[str, float]
    mse: float
    accuracy: float   # fraction of phenotypes within threshold 0.15




class ExperimentSession:
    def __init__(
        self,
        organism: Organism,
        budget: int = 20,
        seed: int | None = None,
    ):
        self.organism = organism
        self.budget = budget
        self.budget_used = 0
        self._rng = np.random.default_rng(seed)
        self._rng_py = random.Random(seed)

        self._prediction_results: list[PredictionResult] = []
        self._hypothesis: str | None = None
        self._experiment_log: list[dict] = []

        # Disease mode state
        self._is_disease = bool(organism.malfunctions)
        self._malfunction_guess: dict | None = None
        self._hypothesis_locked: bool = False   # True after first hypothesis submission
        self._rescue_results: list[dict] = []

        # Generate prediction tasks on init
        self._tasks: dict[str, PredictionTask] = {}
        self._generate_tasks(n=2)

    # ------------------------------------------------------------------
    # Task generation (hidden ground truth)
    # ------------------------------------------------------------------

    def _generate_tasks(self, n: int = 2) -> None:
        """
        Generate n prediction tasks using cross-module double-gene interventions.

        Each task targets one gene from each of two different modules, so the
        agent cannot solve it by directly looking up a single-gene experiment.
        Only observable (non-latent) genes are targeted.
        """
        iv_types = ["BLOCK", "BOOST", "DAMPEN"]
        latent_ids = set(self.organism.latent_genes)
        modules_with_genes = [
            m for m in self.organism.modules
            if any(gid not in latent_ids for gid in m.gene_ids)
        ]
        gene_ids = [g.id for g in self.organism.genes if g.id not in latent_ids]

        for i in range(n):
            if len(modules_with_genes) >= 2:
                # Cross-module: one observable gene from each of two different modules
                mod_a, mod_b = self._rng_py.sample(modules_with_genes, 2)
                target_ids = [
                    self._rng_py.choice([g for g in mod_a.gene_ids if g not in latent_ids]),
                    self._rng_py.choice([g for g in mod_b.gene_ids if g not in latent_ids]),
                ]
            else:
                # Fallback: any 2 distinct genes
                target_ids = self._rng_py.sample(gene_ids, min(2, len(gene_ids)))

            interventions = {
                gid: {"type": self._rng_py.choice(iv_types)}
                for gid in target_ids
            }
            result = simulate_sigmoid(
                self.organism,
                interventions=interventions,
                active_signals={},
                rng=np.random.default_rng(int(self._rng.integers(0, 2**31))),
            )
            task_id = f"task_{i:02d}"
            self._tasks[task_id] = PredictionTask(
                id=task_id,
                interventions=interventions,
                ground_truth=result["phenotypes"],
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_info(self) -> dict[str, Any]:
        """Free: returns organism info visible to agent."""
        latent_ids = set(self.organism.latent_genes)
        gene_names = [g.name for g in self.organism.genes if g.id not in latent_ids]
        signal_info = [
            {"label": s.label, "mode": s.mode}
            for s in self.organism.signals
        ]
        phenotype_labels = [p.label for p in self.organism.phenotypes]
        baseline_phenotypes = self._compute_baseline_phenotypes()

        info: dict[str, Any] = {
            "organism_id": self.organism.id,
            "gene_names": gene_names,
            "signals": signal_info,
            "observable_phenotypes": phenotype_labels,
            "budget_remaining": self.budget - self.budget_used,
            "budget_total": self.budget,
            "baseline_phenotypes": baseline_phenotypes,
        }

        if self._is_disease:
            org = self.organism
            disease_phenos = baseline_phenotypes  # already computed above
            aberrant = [
                label for label, val in disease_phenos.items()
                if not (
                    org.healthy_phenotype_ranges[label][0]
                    <= val
                    <= org.healthy_phenotype_ranges[label][1]
                )
            ]
            info["cell_type"] = org.cell_type.label if org.cell_type else None
            info["cell_type_description"] = (
                org.cell_type.description if org.cell_type else None
            )
            info["healthy_phenotype_ranges"] = {
                k: list(v) for k, v in org.healthy_phenotype_ranges.items()
            }
            info["aberrant_phenotypes"] = aberrant

        return info

    def get_next_prediction_task(self) -> dict[str, Any]:
        """
        Free: reveal the next prediction task.

        Tasks are revealed one at a time. Submit your prediction for the current
        task before calling this again — the next task is only revealed once the
        previous one has been submitted.

        Tasks use cross-module double-gene interventions that you are unlikely
        to have directly measured. Reason from your causal model.
        """
        submitted_ids = {r.task_id for r in self._prediction_results}
        gene_id_to_name = {g.id: g.name for g in self.organism.genes}

        for tid, task in self._tasks.items():
            if tid not in submitted_ids:
                iv_by_name = {
                    gene_id_to_name.get(gid, gid): iv
                    for gid, iv in task.interventions.items()
                }
                tasks_remaining = len(self._tasks) - len(submitted_ids)
                return {
                    "task_id": tid,
                    "interventions": iv_by_name,
                    "tasks_remaining": tasks_remaining,
                    "note": (
                        "Submit your prediction via submit_prediction(task_id, "
                        "{phenotype_label: value}), then call get_next_prediction_task() "
                        "again for the next task."
                    ),
                }

        return {
            "done": True,
            "message": "All prediction tasks have been submitted.",
            "tasks_submitted": len(submitted_ids),
        }

    def run_experiment(
        self,
        interventions: dict[str, Any],
        active_signals: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Cost 1. Run a perturbation experiment.
        interventions: {gene_name → {"type": "BLOCK"|"BOOST"|"DAMPEN"}} or
                       {signal_label → "activate"}
        Returns phenotype readout + dynamics status.
        """
        if self.budget_used >= self.budget:
            return {"error": "Budget exhausted"}

        # Translate gene names to IDs
        name_to_id = {g.name: g.id for g in self.organism.genes}
        label_to_signal = {s.label: s for s in self.organism.signals}
        latent_ids = set(self.organism.latent_genes)

        gene_interventions: dict[str, Any] = {}
        signal_overrides: dict[str, float] = {}

        for key, val in interventions.items():
            if key in name_to_id:
                gid = name_to_id[key]
                if gid in latent_ids:
                    return {"error": f"Gene {key} is not accessible for intervention"}
                gene_interventions[gid] = val
            elif key in label_to_signal:
                sig = label_to_signal[key]
                # "activate" → use signal's default strength
                mult = 1.0 if val in ("activate", "activates") else -1.0
                signal_overrides[sig.id] = mult * sig.strength
            else:
                return {"error": f"Unknown target: {key}"}

        if active_signals:
            signal_overrides.update(active_signals)

        result = simulate_sigmoid(
            self.organism,
            interventions=gene_interventions,
            active_signals=signal_overrides,
            rng=self._rng,
        )

        self.budget_used += 1
        log_entry = {
            "experiment_idx": self.budget_used,
            "interventions": interventions,
            "gene_state": result["final_state"],
            "phenotypes": result["phenotypes"],
            "status": result["status"],
            "steps": result["steps"],
        }
        self._experiment_log.append(log_entry)

        return {
            "phenotypes": result["phenotypes"],
            "status": result["status"],
            "steps": result["steps"],
            "budget_remaining": self.budget - self.budget_used,
        }

    def submit_prediction(
        self,
        task_id: str,
        prediction: dict[str, float],
    ) -> dict[str, Any]:
        """Cost 0. Score a prediction for a task."""
        if task_id not in self._tasks:
            return {"error": f"Unknown task_id: {task_id}"}

        task = self._tasks[task_id]
        gt = task.ground_truth
        phenotype_labels = list(gt.keys())

        mse_sum = 0.0
        correct = 0
        threshold = 0.15
        details: dict[str, dict] = {}
        for label in phenotype_labels:
            gt_val = gt[label]
            pred_val = prediction.get(label, 0.5)
            err = (gt_val - pred_val) ** 2
            mse_sum += err
            within = abs(gt_val - pred_val) <= threshold
            if within:
                correct += 1
            details[label] = {
                "ground_truth": round(gt_val, 4),
                "prediction": round(pred_val, 4),
                "within_threshold": within,
            }

        mse = mse_sum / max(len(phenotype_labels), 1)
        accuracy = correct / max(len(phenotype_labels), 1)

        res = PredictionResult(
            task_id=task_id,
            prediction=prediction,
            mse=mse,
            accuracy=accuracy,
        )
        self._prediction_results.append(res)

        return {
            "task_id": task_id,
            "mse": round(mse, 4),
            "accuracy": round(accuracy, 4),
            "details": details,
        }

    def submit_hypothesis(self, text: str) -> dict[str, Any]:
        """Cost 0. Store a free-text hypothesis."""
        self._hypothesis = text
        return {"stored": True, "length": len(text)}

    def test_rescue(
        self,
        interventions: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Cost 1. Test whether a proposed intervention restores aberrant phenotypes
        to healthy ranges. Runs simulate_sigmoid from the disease baseline.

        Requires: submit_malfunction_hypothesis() must be called first.

        interventions: {gene_name → {"type": "BLOCK"|"BOOST"|"DAMPEN"}} or
                       {signal_label → "activate"}
        """
        if not self._is_disease:
            return {"error": "not a disease organism"}
        if not self._hypothesis_locked:
            return {"error": "submit_malfunction_hypothesis() must be called before test_rescue()"}
        if self.budget_used >= self.budget:
            return {"error": "Budget exhausted"}

        # Translate names to IDs (same logic as run_experiment)
        name_to_id = {g.name: g.id for g in self.organism.genes}
        label_to_signal = {s.label: s for s in self.organism.signals}
        latent_ids = set(self.organism.latent_genes)

        gene_interventions: dict[str, Any] = {}
        signal_overrides: dict[str, float] = {}

        for key, val in interventions.items():
            if key in name_to_id:
                gid = name_to_id[key]
                if gid in latent_ids:
                    return {"error": f"Gene {key} is not accessible for intervention"}
                gene_interventions[gid] = val
            elif key in label_to_signal:
                sig = label_to_signal[key]
                mult = 1.0 if val in ("activate", "activates") else -1.0
                signal_overrides[sig.id] = mult * sig.strength
            else:
                return {"error": f"Unknown target: {key}"}

        result = simulate_sigmoid(
            self.organism,
            interventions=gene_interventions,
            active_signals=signal_overrides,
            rng=self._rng,
        )
        self.budget_used += 1

        rescue_phenos = result["phenotypes"]
        org = self.organism
        phenotype_in_range: dict[str, bool] = {}
        healthy_phenos = _compute_phenotypes_from_state(
            self.organism, org.healthy_baseline
        )
        mse_sum = 0.0
        restored = 0
        total = len(org.healthy_phenotype_ranges)
        for label, (lo, hi) in org.healthy_phenotype_ranges.items():
            val = rescue_phenos.get(label, 0.5)
            in_range = lo <= val <= hi
            phenotype_in_range[label] = in_range
            if in_range:
                restored += 1
            healthy_val = healthy_phenos.get(label, 0.5)
            mse_sum += (val - healthy_val) ** 2

        restored_fraction = restored / max(total, 1)
        mse_vs_healthy = mse_sum / max(total, 1)

        rescue_result = {
            "interventions": interventions,
            "phenotypes": rescue_phenos,
            "phenotype_in_healthy_range": phenotype_in_range,
            "restored_fraction": round(restored_fraction, 4),
            "mse_vs_healthy": round(mse_vs_healthy, 4),
            "budget_remaining": self.budget - self.budget_used,
        }
        self._rescue_results.append(rescue_result)
        return rescue_result

    def submit_malfunction_hypothesis(
        self,
        target_name: str,
        malfunction_type: str,
    ) -> dict[str, Any]:
        """
        Cost 0. Submit a hypothesis about the malfunction. One submission only —
        locked immediately. Unlocks test_rescue(). Score is revealed at session end
        via get_summary(), not returned here.

        target_name: gene name (e.g. 'G007') or signal label
        malfunction_type: 'LOCK_HI' | 'LOCK_LO' | 'PERSIST'
        """
        if not self._is_disease:
            return {"error": "not a disease organism"}
        if self._hypothesis_locked:
            return {"error": "hypothesis already submitted and locked; score revealed at session end"}

        score = 0.0
        feedback = "wrong target"
        for m in self.organism.malfunctions:
            if m.target_name == target_name:
                if m.type == malfunction_type:
                    score = 1.0
                    feedback = "exact match"
                else:
                    score = max(score, 0.5)
                    feedback = f"correct target but wrong type (actual: {m.type})"
                break

        self._malfunction_guess = {
            "target_name": target_name,
            "malfunction_type": malfunction_type,
            "score": score,
            "feedback": feedback,
        }
        self._hypothesis_locked = True
        return {
            "stored": True,
            "note": "Hypothesis locked. test_rescue() is now available. Score revealed at session end.",
        }

    def get_summary(self) -> dict[str, Any]:
        """Return all scores and budget usage."""
        pred_summary = []
        for r in self._prediction_results:
            pred_summary.append({
                "task_id": r.task_id,
                "mse": round(r.mse, 4),
                "accuracy": round(r.accuracy, 4),
            })

        avg_mse = (
            sum(r.mse for r in self._prediction_results) / len(self._prediction_results)
            if self._prediction_results else None
        )
        avg_acc = (
            sum(r.accuracy for r in self._prediction_results) / len(self._prediction_results)
            if self._prediction_results else None
        )

        summary: dict[str, Any] = {
            "organism_id": self.organism.id,
            "budget_total": self.budget,
            "budget_used": self.budget_used,
            "prediction_results": pred_summary,
            "avg_mse": round(avg_mse, 4) if avg_mse is not None else None,
            "avg_accuracy": round(avg_acc, 4) if avg_acc is not None else None,
            "hypothesis": self._hypothesis,
            "n_experiments": len(self._experiment_log),
        }

        if self._is_disease:
            summary["malfunction_hypothesis"] = self._malfunction_guess
            summary["rescue_results"] = self._rescue_results

        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_baseline_phenotypes(self) -> dict[str, float]:
        from .dynamics import compute_phenotypes
        return compute_phenotypes(
            self.organism,
            self.organism.baseline_state,
            rng=np.random.default_rng(0),
            noise=False,
        )


def _compute_phenotypes_from_state(
    organism,
    state: dict[str, float],
) -> dict[str, float]:
    """Module-level helper used by test_rescue."""
    from .dynamics import compute_phenotypes
    return compute_phenotypes(organism, state, rng=np.random.default_rng(0), noise=False)
