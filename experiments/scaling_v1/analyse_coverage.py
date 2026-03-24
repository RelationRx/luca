"""
Gene coverage and exploration efficiency analysis — post-hoc, no API calls needed.

Computes per-session coverage and three efficiency metrics that characterise
how close each model's exploration strategy is to optimal.

Metrics
-------
coverage_fraction
    Unique genes perturbed / total genes. Basic exploration breadth.

efficiency_1  (task-specific empirical)
    Fraction of prediction-task genes actually perturbed by the agent.
    The prediction tasks specify which genes are intervened on — an agent
    that perturbs those genes has the most relevant information.

efficiency_2  (phenotype-structural)
    Fraction of phenotype-contributing genes (from gene_phenotype_edges
    ground truth) that the agent perturbed. These are the genes that
    directly determine prediction outcomes.

efficiency_3  (information-theoretic)
    n_experiments / (k * log2(N)), where k = number of gene→phenotype
    edges and N = total genes. The compressed-sensing lower bound on
    experiments needed to identify k sparse edges in an N-dimensional
    system. Values < 1 = below theoretical minimum; ≥ 1 = sufficient.
    Reference: sparse recovery / compressed sensing (Candès & Tao 2006).

Usage
-----
    python experiments/scaling_v1/analyse_coverage.py
    python experiments/scaling_v1/analyse_coverage.py --model claude-sonnet-4-6
"""
from __future__ import annotations

import json
import math
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

    # Ground truth: gene→phenotype edges
    gt_edges = meta.get("ground_truth", {}).get("gene_phenotype_edges", [])
    phenotype_genes: set[str] = {e["from"] for e in gt_edges}
    k = len(gt_edges)  # sparsity: number of nonzero edges

    # Prediction task genes (from tool call results)
    task_genes: set[str] = set()
    for turn in log["turns"]:
        for tc in turn.get("tool_calls", []):
            if tc.get("tool") == "get_next_prediction_task":
                result = tc.get("result", {})
                if isinstance(result, dict):
                    for gene in (result.get("interventions") or {}).keys():
                        task_genes.add(gene)

    # Genes the agent actually perturbed
    seen_genes: set[str] = set()
    n_experiments = 0
    for turn in log["turns"]:
        for tc in turn.get("tool_calls", []):
            if tc.get("tool") == "run_experiment":
                interventions = _parse_interventions(tc.get("input", {}))
                for gene in interventions:
                    seen_genes.add(gene)
                n_experiments += 1

    if n_experiments == 0:
        return None

    # Efficiency 1: task-specific empirical
    eff1 = (len(task_genes & seen_genes) / len(task_genes)
            if task_genes else None)

    # Efficiency 2: phenotype-structural
    eff2 = (len(phenotype_genes & seen_genes) / len(phenotype_genes)
            if phenotype_genes else None)

    # Efficiency 3: information-theoretic (compressed sensing lower bound)
    # min_experiments = k * log2(N); ratio = actual / minimum
    eff3 = (n_experiments / (k * math.log2(n_genes))
            if k > 0 and n_genes > 1 else None)

    return {
        "model": model,
        "seed": seed,
        "n_genes": n_genes,
        "budget_total": budget_total,
        "n_experiments": n_experiments,
        "budget_used_fraction": round(n_experiments / budget_total, 3),
        "unique_genes": len(seen_genes),
        "coverage_fraction": round(len(seen_genes) / n_genes, 3),
        "k_edges": k,
        "n_task_genes": len(task_genes),
        "efficiency_1_task": round(eff1, 3) if eff1 is not None else None,
        "efficiency_2_phenotype": round(eff2, 3) if eff2 is not None else None,
        "efficiency_3_it": round(eff3, 3) if eff3 is not None else None,
        "it_lower_bound": round(k * math.log2(n_genes), 1) if k > 0 and n_genes > 1 else None,
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

    print(f"\nGene coverage & exploration efficiency — scaling study\n")

    for model in models:
        model_recs = [r for r in records if r["model"] == model]
        print(f"{'─'*90}")
        print(f"Model: {model}")
        print(f"  {'N':>6}  {'Coverage':>12}  {'Eff-1 task':>12}  "
              f"{'Eff-2 pheno':>12}  {'Eff-3 IT':>10}  {'IT bound':>10}  {'n':>4}")
        for n in n_values:
            recs = [r for r in model_recs if r["n_genes"] == n and not r["stalled"]]
            if not recs:
                continue
            print(
                f"  {n:>6}  "
                f"{_mean_std([r['coverage_fraction'] for r in recs]):>12}  "
                f"{_mean_std([r['efficiency_1_task'] for r in recs]):>12}  "
                f"{_mean_std([r['efficiency_2_phenotype'] for r in recs]):>12}  "
                f"{_mean_std([r['efficiency_3_it'] for r in recs]):>10}  "
                f"{_mean_std([r['it_lower_bound'] for r in recs if r['it_lower_bound']]):>10}  "
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
