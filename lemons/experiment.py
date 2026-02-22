"""ExperimentSession — budget-limited perturbation interface."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .dynamics import simulate_sigmoid
from .schema import Organism


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


@dataclass
class ModuleResult:
    ari: float
    nmi: float


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
        self._module_result: ModuleResult | None = None
        self._hypothesis: str | None = None
        self._experiment_log: list[dict] = []

        # Generate prediction tasks on init
        self._tasks: dict[str, PredictionTask] = {}
        self._generate_tasks(n=5)

    # ------------------------------------------------------------------
    # Task generation (hidden ground truth)
    # ------------------------------------------------------------------

    def _generate_tasks(self, n: int = 5) -> None:
        gene_ids = [g.id for g in self.organism.genes]
        for i in range(n):
            # Random 1–2 gene interventions
            n_iv = self._rng_py.randint(1, 2)
            target_genes = self._rng_py.sample(gene_ids, min(n_iv, len(gene_ids)))
            iv_types = ["KO", "OE", "KD"]
            interventions = {
                gid: {"type": self._rng_py.choice(iv_types)}
                for gid in target_genes
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
        gene_names = [g.name for g in self.organism.genes]
        signal_info = [
            {"label": s.label, "mode": s.mode}
            for s in self.organism.signals
        ]
        phenotype_labels = [p.label for p in self.organism.phenotypes]
        baseline_phenotypes = self._compute_baseline_phenotypes()

        # Describe tasks using gene NAMES (not IDs)
        gene_id_to_name = {g.id: g.name for g in self.organism.genes}
        task_descriptions = []
        for tid, task in self._tasks.items():
            iv_by_name = {
                gene_id_to_name.get(gid, gid): iv
                for gid, iv in task.interventions.items()
            }
            task_descriptions.append({"id": tid, "interventions": iv_by_name})

        return {
            "organism_id": self.organism.id,
            "gene_names": gene_names,
            "signals": signal_info,
            "observable_phenotypes": phenotype_labels,
            "budget_remaining": self.budget - self.budget_used,
            "budget_total": self.budget,
            "baseline_phenotypes": baseline_phenotypes,
            "prediction_tasks": task_descriptions,
        }

    def run_experiment(
        self,
        interventions: dict[str, Any],
        active_signals: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Cost 1. Run a perturbation experiment.
        interventions: {gene_name → {"type": "KO"|"OE"|"KD"}} or
                       {signal_label → "activate"}
        Returns phenotype readout + dynamics status.
        """
        if self.budget_used >= self.budget:
            return {"error": "Budget exhausted"}

        # Translate gene names to IDs
        name_to_id = {g.name: g.id for g in self.organism.genes}
        label_to_signal = {s.label: s for s in self.organism.signals}

        gene_interventions: dict[str, Any] = {}
        signal_overrides: dict[str, float] = {}

        for key, val in interventions.items():
            if key in name_to_id:
                gene_interventions[name_to_id[key]] = val
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

    def submit_module_assignment(
        self,
        assignments: dict[str, str],
    ) -> dict[str, Any]:
        """
        Cost 0. Score module assignment.
        assignments: {gene_name → module_label_or_id}
        Returns ARI and NMI vs ground truth.
        """
        from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

        name_to_id = {g.name: g.id for g in self.organism.genes}
        gene_ids = [g.id for g in self.organism.genes]

        # Ground truth labels
        gt_labels: list[int] = []
        pred_labels: list[int] = []

        # Map module label/id to integer
        pred_module_set = sorted(set(assignments.values()))
        pred_module_map = {m: i for i, m in enumerate(pred_module_set)}

        # Ground truth map: gene_id → module_index
        gt_module_map: dict[str, int] = {}
        for k, mod in enumerate(self.organism.modules):
            for gid in mod.gene_ids:
                gt_module_map[gid] = k

        for gname, pred_mod in assignments.items():
            gid = name_to_id.get(gname)
            if gid is None:
                continue
            gt_labels.append(gt_module_map.get(gid, -1))
            pred_labels.append(pred_module_map.get(pred_mod, -1))

        if not gt_labels:
            return {"error": "No valid gene assignments"}

        ari = float(adjusted_rand_score(gt_labels, pred_labels))
        nmi = float(normalized_mutual_info_score(gt_labels, pred_labels))

        self._module_result = ModuleResult(ari=ari, nmi=nmi)
        return {"ari": round(ari, 4), "nmi": round(nmi, 4)}

    def submit_hypothesis(self, text: str) -> dict[str, Any]:
        """Cost 0. Store a free-text hypothesis."""
        self._hypothesis = text
        return {"stored": True, "length": len(text)}

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

        return {
            "organism_id": self.organism.id,
            "budget_total": self.budget,
            "budget_used": self.budget_used,
            "prediction_results": pred_summary,
            "avg_mse": round(avg_mse, 4) if avg_mse is not None else None,
            "avg_accuracy": round(avg_acc, 4) if avg_acc is not None else None,
            "module_assignment": (
                {"ari": self._module_result.ari, "nmi": self._module_result.nmi}
                if self._module_result else None
            ),
            "hypothesis": self._hypothesis,
            "n_experiments": len(self._experiment_log),
        }

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
