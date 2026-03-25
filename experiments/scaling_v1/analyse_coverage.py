"""
Gene coverage and exploration efficiency analysis — post-hoc, no API calls needed.

Computes per-session coverage and two hit-rate metrics that characterise
whether an agent explores task-relevant genes before or after seeing the tasks.

Metrics
-------
coverage_fraction
    Unique genes perturbed / total genes. Basic exploration breadth.

prospective_task_hit
    Fraction of prediction-task genes perturbed *before* the agent called
    get_next_prediction_task() for the first time. Measures genuine unsupervised
    exploration of task-relevant genes — the agent had no knowledge of which
    genes would be tested.

targeted_task_hit
    Fraction of prediction-task genes perturbed *after* the first task reveal.
    Measures deliberate follow-up once the agent knows which genes matter.

Usage
-----
    python experiments/scaling_v1/analyse_coverage.py
    python experiments/scaling_v1/analyse_coverage.py --model claude-sonnet-4-6
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from experiments.scaling_v1.analyse_strategy import _parse_interventions

REPO_ROOT = Path(__file__).parent.parent.parent


def analyse_coverage(log_path: Path) -> dict | None:
    log = json.loads(log_path.read_text())
    if "turns" not in log or not log["turns"]:
        return None

    meta = log.get("metadata", {})
    model = meta.get("model", log_path.stem.split("_seed")[0])
    seed = meta.get("seed")
    n_genes = meta.get("n_genes") or int(log_path.parent.parent.name.lstrip("N"))
    summary = log.get("summary", {})
    budget_total = summary.get("budget_total", 0)
    if budget_total == 0:
        return None

    # Single pass: track experiment index, task reveal index, genes seen before/after
    seen_genes: set[str] = set()         # all genes ever perturbed
    seen_genes_before: set[str] = set()  # genes perturbed before first prediction task reveal
    task_genes: set[str] = set()
    first_pred_exp_idx: int | None = None
    n_experiments = 0

    for turn in log["turns"]:
        for tc in turn.get("tool_calls", []):
            tool = tc.get("tool")
            if tool == "run_experiment":
                interventions = _parse_interventions(tc.get("input", {}))
                for gene in interventions:
                    seen_genes.add(gene)
                    if first_pred_exp_idx is None:
                        seen_genes_before.add(gene)
                n_experiments += 1
            elif tool == "get_next_prediction_task":
                result = tc.get("result", {})
                if isinstance(result, dict):
                    for gene in (result.get("interventions") or {}).keys():
                        task_genes.add(gene)
                    if first_pred_exp_idx is None:
                        first_pred_exp_idx = n_experiments

    if n_experiments == 0:
        return None

    # Prospective hit: task genes perturbed before seeing any task (genuine signal)
    prospective = (len(task_genes & seen_genes_before) / len(task_genes)
                   if task_genes else None)

    # Targeted hit: task genes perturbed after the first task reveal (deliberate follow-up)
    seen_genes_after = seen_genes - seen_genes_before
    targeted = (len(task_genes & seen_genes_after) / len(task_genes)
                if task_genes else None)

    return {
        "model": model,
        "seed": seed,
        "n_genes": n_genes,
        "budget_total": budget_total,
        "n_experiments": n_experiments,
        "budget_used_fraction": round(n_experiments / budget_total, 3),
        "unique_genes": len(seen_genes),
        "coverage_fraction": round(len(seen_genes) / n_genes, 3),
        "n_task_genes": len(task_genes),
        "first_pred_exp_idx": first_pred_exp_idx,
        "prospective_task_hit": round(prospective, 3) if prospective is not None else None,
        "targeted_task_hit": round(targeted, 3) if targeted is not None else None,
        "stalled": any(t.get("stall") for t in log["turns"]),
    }


def _mean_std(values: list[float]) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return "n/a"
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return f"{m:.3f}±{s:.3f}"


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    logs_base = Path(__file__).parent / "logs"
    if not logs_base.exists():
        print(f"No logs found at {logs_base}")
        return

    records: list[dict] = []
    for sweep_dir in sorted(logs_base.iterdir()):
        logs_dir = sweep_dir / "logs"
        if not logs_dir.exists():
            continue
        for log_file in sorted(logs_dir.glob("*.json")):
            r = analyse_coverage(log_file)
            if r is None:
                continue
            if args.model and r["model"] != args.model:
                continue
            records.append(r)

    if not records:
        print("No records parsed.")
        return

    models = sorted({r["model"] for r in records})
    n_values = sorted({r["n_genes"] for r in records if r["n_genes"] is not None})

    print(f"\nGene coverage & task hit rates — scaling study\n")

    for model in models:
        model_recs = [r for r in records if r["model"] == model]
        print(f"{'─'*90}")
        print(f"Model: {model}")
        print(f"  {'N':>6}  {'Coverage':>12}  {'Prospective hit':>16}  {'Targeted hit':>13}  {'n':>4}")
        for n in n_values:
            recs = [r for r in model_recs if r["n_genes"] == n and not r["stalled"]]
            if not recs:
                continue
            print(
                f"  {n:>6}  "
                f"{_mean_std([r['coverage_fraction'] for r in recs]):>12}  "
                f"{_mean_std([r['prospective_task_hit'] for r in recs]):>16}  "
                f"{_mean_std([r['targeted_task_hit'] for r in recs]):>13}  "
                f"{len(recs):>4}"
            )
        print()

    out_path = Path(__file__).parent / "coverage_analysis.jsonl"
    with open(out_path, "w") as f:
        for r in sorted(records, key=lambda x: (x["model"], x["n_genes"] or 0, x["seed"] or 0)):
            f.write(json.dumps(r) + "\n")
    print(f"Per-session records → {out_path}")


if __name__ == "__main__":
    main()
