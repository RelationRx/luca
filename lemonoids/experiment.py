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
    accuracy: float   # fraction of phenotypes within threshold 0.10




class ExperimentSession:
    def __init__(
        self,
        organism: Organism,
        budget: int | None = None,
        seed: int | None = None,
        n_prediction_tasks: int = 2,
        active_tasks: frozenset[str] | None = None,
    ):
        self.organism = organism
        self.budget = budget if budget is not None else recommended_budget(organism)
        self.budget_used = 0
        self._seed = seed  # stored for deterministic per-experiment RNG
        self._rng = np.random.default_rng(seed)
        self._rng_py = random.Random(seed)

        self._active_tasks: frozenset[str] = (
            active_tasks if active_tasks is not None
            else frozenset({"predict", "diagnose", "rescue"})
        )

        self._prediction_results: list[PredictionResult] = []
        self._hypothesis: str | None = None
        self._experiment_log: list[dict] = []

        # Disease mode state
        self._is_disease = bool(organism.malfunctions)
        self._malfunction_guess: dict | None = None
        self._hypothesis_locked: bool = False   # True after first hypothesis submission
        self._rescue_results: list[dict] = []

        # Network reconstruction state
        self._submitted_network: list[dict] | None = None

        # Generate prediction tasks on init (skipped if predict task is not active)
        self._tasks: dict[str, PredictionTask] = {}
        if "predict" in self._active_tasks:
            self._generate_tasks(n=n_prediction_tasks)

    # ------------------------------------------------------------------
    # Task generation (hidden ground truth)
    # ------------------------------------------------------------------

    def _generate_tasks(self, n: int = 2, min_shift: float = 0.1, max_retries: int = 20) -> None:
        """
        Generate n prediction tasks using cross-module double-gene interventions.

        Each task targets one gene from each of two different modules, so the
        agent cannot solve it by directly looking up a single-gene experiment.
        Only observable (non-latent) genes are targeted.

        Non-triviality guarantee: each task retries up to max_retries times to find
        interventions where at least one phenotype shifts by ≥ min_shift from baseline.
        This ensures prediction tasks require genuine causal reasoning rather than
        "predict baseline and score well". If no non-trivial task is found after
        max_retries, the attempt with the largest shift is used.
        """
        iv_types = ["BLOCK", "BOOST", "DAMPEN"]
        latent_ids = set(self.organism.latent_genes)
        gene_ids = [g.id for g in self.organism.genes if g.id not in latent_ids]
        baseline = self._compute_baseline_phenotypes()

        # Build phenotype → gene candidates map so tasks can target genes that
        # share a readout. Shared-readout pairs interact via the same sigmoid,
        # making additive prediction inaccurate — the task genuinely requires
        # reasoning about the combined regulatory input.
        ph_to_genes: list[list[str]] = [
            [gid for gid in ph.readout.depends_on if gid not in latent_ids]
            for ph in self.organism.phenotypes
        ]
        # Only use phenotypes that have ≥2 candidates for intra-phenotype sampling
        shared_readout_phs = [gs for gs in ph_to_genes if len(gs) >= 2]

        for i in range(n):
            best_interventions = None
            best_result = None
            best_shift = -1.0

            for _attempt in range(max_retries):
                # Prefer two genes that share a phenotype readout: their combined
                # perturbation is non-additive due to sigmoid nonlinearity.
                # Fall back to any two observable genes if no shared-readout pair exists.
                if shared_readout_phs:
                    ph_genes = self._rng_py.choice(shared_readout_phs)
                    target_ids = self._rng_py.sample(ph_genes, 2)
                else:
                    target_ids = self._rng_py.sample(gene_ids, min(2, len(gene_ids)))

                interventions = {
                    gid: {"type": self._rng_py.choice(iv_types)}
                    for gid in target_ids
                }
                result = simulate_sigmoid(
                    self.organism,
                    interventions=interventions,
                    active_signals={},
                    rng=np.random.default_rng([self._seed if self._seed is not None else 0,
                                               65536 + i * 100 + _attempt]),
                )
                max_shift = max(
                    abs(result["phenotypes"].get(lbl, 0.5) - baseline.get(lbl, 0.5))
                    for lbl in baseline
                )
                if max_shift > best_shift:
                    best_shift = max_shift
                    best_interventions = interventions
                    best_result = result
                if max_shift >= min_shift:
                    break  # non-trivial task found

            task_id = f"task_{i:02d}"
            self._tasks[task_id] = PredictionTask(
                id=task_id,
                interventions=best_interventions,
                ground_truth=best_result["phenotypes"],
            )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def is_disease(self) -> bool:
        """True if this session is running a disease organism."""
        return self._is_disease

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_interventions(
        self, interventions: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, float]] | dict:
        """
        Translate agent-facing intervention dict to internal gene/signal IDs.

        Returns (gene_interventions, signal_overrides) on success,
        or {"error": str} on failure.
        """
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

        return gene_interventions, signal_overrides

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
                obs_phenotypes = [p.label for p in self.organism.phenotypes]
                return {
                    "task_id": tid,
                    "interventions": iv_by_name,
                    "tasks_remaining": tasks_remaining,
                    "phenotype_labels": obs_phenotypes,
                    "note": (
                        f"Call submit_prediction with task_id='{tid}' and a 'prediction' object "
                        f"mapping each phenotype label to a float [0.0, 1.0]. "
                        f"Required format: {{\"task_id\": \"{tid}\", \"prediction\": "
                        f"{{{', '.join(repr(l) + ': <float>' for l in obs_phenotypes)}}}}}. "
                        "Then call get_next_prediction_task() for the next task."
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

        resolved = self._resolve_interventions(interventions)
        if isinstance(resolved, dict):
            return resolved  # error
        gene_interventions, signal_overrides = resolved

        if active_signals:
            signal_overrides.update(active_signals)

        result = simulate_sigmoid(
            self.organism,
            interventions=gene_interventions,
            active_signals=signal_overrides,
            rng=np.random.default_rng([self._seed if self._seed is not None else 0,
                                       self.budget_used]),
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
        threshold = 0.10
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

    def submit_network(self, edges: list[dict]) -> dict[str, Any]:
        """
        Cost 0. Submit a reconstructed gene-regulatory network as a list of
        gene → phenotype edges inferred from your experiments.

        Each edge is a dict with:
          - "gene":      gene name (e.g. "G007")
          - "phenotype": phenotype label (e.g. "adaptation-score")
          - "direction": "activates" or "inhibits" (optional)

        Example:
          [
            {"gene": "G007", "phenotype": "adaptation-score", "direction": "activates"},
            {"gene": "G012", "phenotype": "recovery-index", "direction": "inhibits"},
          ]

        Can be called at most once. Precision/recall/F1 against ground truth
        are revealed at session end via get_summary(). Ground truth is the set
        of observable gene → phenotype readout edges; latent gene contributions
        are excluded (they are unknowable from perturbation experiments alone).
        """
        if self._submitted_network is not None:
            return {"error": "network already submitted; score revealed at session end"}

        gene_names = {g.name for g in self.organism.genes}
        ph_labels = {p.label for p in self.organism.phenotypes}
        valid_directions = {"activates", "inhibits"}

        validated: list[dict] = []
        errors: list[str] = []
        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append(f"edge {i}: must be a dict")
                continue
            gene = edge.get("gene")
            phenotype = edge.get("phenotype")
            direction = edge.get("direction")
            if gene not in gene_names:
                errors.append(f"edge {i}: unknown gene '{gene}'")
            elif phenotype not in ph_labels:
                errors.append(f"edge {i}: unknown phenotype '{phenotype}'")
            elif direction is not None and direction not in valid_directions:
                errors.append(f"edge {i}: direction must be 'activates' or 'inhibits', got '{direction}'")
            else:
                validated.append({"gene": gene, "phenotype": phenotype, "direction": direction})

        if errors:
            return {"error": f"Invalid edges: {errors[:5]}"}  # show first 5

        self._submitted_network = validated
        return {
            "stored": True,
            "n_edges": len(validated),
            "note": "Network stored. Precision/recall/F1 revealed at session end via get_summary().",
        }

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

        resolved = self._resolve_interventions(interventions)
        if isinstance(resolved, dict):
            return resolved  # error
        gene_interventions, signal_overrides = resolved

        result = simulate_sigmoid(
            self.organism,
            interventions=gene_interventions,
            active_signals=signal_overrides,
            rng=np.random.default_rng([self._seed if self._seed is not None else 0,
                                       self.budget_used]),
        )
        self.budget_used += 1

        rescue_phenos = result["phenotypes"]
        org = self.organism
        phenotype_in_range: dict[str, bool] = {}
        healthy_phenos = self._compute_phenotypes_from_state(org.healthy_baseline)
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

        Scoring (revealed at session end via get_summary()):
            1.0 — exact match: correct target AND correct malfunction type
            0.5 — correct target, wrong malfunction type
            0.0 — wrong target
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

    def _ground_truth_network_edges(self) -> tuple[set, set]:
        """
        Return ground truth gene→phenotype edges as two sets:
          - undirected: {(gene_name, ph_label)}
          - directed:   {(gene_name, ph_label, direction)}

        Only observable gene edges are included — latent gene contributions
        are unknowable from perturbation experiments alone.
        """
        observable_ids = set(self.organism.observable_genes)
        gene_id_to_name = {g.id: g.name for g in self.organism.genes}
        undirected: set[tuple[str, str]] = set()
        directed: set[tuple[str, str, str]] = set()
        for ph in self.organism.phenotypes:
            for gid, w in zip(ph.readout.depends_on, ph.readout.weights):
                if gid not in observable_ids:
                    continue
                name = gene_id_to_name.get(gid)
                if name is None:
                    continue
                undirected.add((name, ph.label))
                directed.add((name, ph.label, "activates" if w > 0 else "inhibits"))
        return undirected, directed

    def _prf1(self, inferred: set, ground_truth: set) -> dict[str, float]:
        if not inferred or not ground_truth:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        tp = len(inferred & ground_truth)
        p = tp / len(inferred)
        r = tp / len(ground_truth)
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}

    def get_summary(self) -> dict[str, Any]:
        """Return all scores and budget usage."""
        threshold = 0.10
        pred_summary = []
        for r in self._prediction_results:
            task = self._tasks[r.task_id]
            per_phenotype = {
                label: {
                    "ground_truth": round(task.ground_truth[label], 4),
                    "prediction": round(r.prediction.get(label, 0.5), 4),
                }
                for label in task.ground_truth
            }
            pred_summary.append({
                "task_id": r.task_id,
                "mse": round(r.mse, 4),
                "accuracy": round(r.accuracy, 4),
                "phenotypes": per_phenotype,
            })

        avg_mse = (
            sum(r.mse for r in self._prediction_results) / len(self._prediction_results)
            if self._prediction_results else None
        )
        avg_acc = (
            sum(r.accuracy for r in self._prediction_results) / len(self._prediction_results)
            if self._prediction_results else None
        )

        baseline_phenotypes = {
            k: round(v, 4) for k, v in self._compute_baseline_phenotypes().items()
        }

        summary: dict[str, Any] = {
            "organism_id": self.organism.id,
            "budget_total": self.budget,
            "budget_used": self.budget_used,
            "active_tasks": sorted(self._active_tasks),
            "accuracy_threshold": threshold,
            "baseline_phenotypes": baseline_phenotypes,
            "prediction_results": pred_summary,
            "avg_mse": round(avg_mse, 4) if avg_mse is not None else None,
            "avg_accuracy": round(avg_acc, 4) if avg_acc is not None else None,
            "hypothesis": self._hypothesis,
            "n_experiments": len(self._experiment_log),
        }

        if self._is_disease:
            org = self.organism
            summary["aberrant_phenotypes"] = {
                label: {
                    "value": round(baseline_phenotypes[label], 4),
                    "healthy_range": [
                        round(org.healthy_phenotype_ranges[label][0], 4),
                        round(org.healthy_phenotype_ranges[label][1], 4),
                    ],
                }
                for label, val in baseline_phenotypes.items()
                if not (
                    org.healthy_phenotype_ranges[label][0]
                    <= val
                    <= org.healthy_phenotype_ranges[label][1]
                )
            }
            summary["true_malfunction"] = [
                {"target_name": m.target_name, "malfunction_type": m.type}
                for m in self.organism.malfunctions
            ]
            summary["malfunction_hypothesis"] = self._malfunction_guess
            summary["rescue_results"] = self._rescue_results
            summary["n_diagnosis_alternatives"] = self.organism.n_diagnosis_alternatives

        # Ground truth network — always present for post-hoc analysis
        gt_undir, gt_dir = self._ground_truth_network_edges()
        summary["ground_truth_network"] = [
            {"gene": gene, "phenotype": ph, "direction": direction}
            for gene, ph, direction in sorted(gt_dir)
        ]

        # Network reconstruction scoring
        if self._submitted_network is not None:
            sub_undir = {(e["gene"], e["phenotype"]) for e in self._submitted_network}
            sub_dir = {
                (e["gene"], e["phenotype"], e["direction"])
                for e in self._submitted_network
                if e.get("direction") is not None
            }
            summary["network_reconstruction"] = {
                "submitted_edges": self._submitted_network,
                "n_submitted": len(sub_undir),
                "n_ground_truth": len(gt_undir),
                "undirected": self._prf1(sub_undir, gt_undir),
                "directed": self._prf1(sub_dir, gt_dir) if sub_dir else None,
            }
        else:
            summary["network_reconstruction"] = None

        return summary

    def _compute_baseline_phenotypes(self) -> dict[str, float]:
        from .dynamics import compute_phenotypes
        return compute_phenotypes(
            self.organism,
            self.organism.baseline_state,
            rng=np.random.default_rng(0),
            noise=False,
        )

    def _compute_phenotypes_from_state(self, state: dict[str, float]) -> dict[str, float]:
        from .dynamics import compute_phenotypes
        return compute_phenotypes(self.organism, state, rng=np.random.default_rng(0), noise=False)
