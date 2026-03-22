"""
Strategy analysis for scaling study — post-hoc, no API calls needed.

For each session log computes three metrics that characterise *how* the agent
uses its budget, then aggregates by model × N.

Metrics
-------
1. prediction_commitment_fraction
   Experiment index of the first get_next_prediction_task() call divided by the
   total budget. 0 = agent committed immediately; 1 = agent used the entire
   budget before asking for a prediction task.

2. intervention_type_mix
   Fraction of run_experiment calls that used BLOCK, BOOST, or DAMPEN.
   Multi-gene experiments count once per gene.

3. redundancy_fraction
   Fraction of run_experiment calls that perturbed a gene already seen earlier
   in the same session. High redundancy = less coherent search strategy.

Usage
-----
    python experiments/scaling_v1/analyse_strategy.py
    python experiments/scaling_v1/analyse_strategy.py --model claude-sonnet-4-6
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def _parse_interventions(inp: dict) -> dict[str, str]:
    """Normalise intervention input to {gene_id: type}. Mirrors agent log format."""
    if "interventions" in inp and isinstance(inp["interventions"], dict):
        ivs = inp["interventions"]
        result: dict[str, str] = {}
        for g, v in ivs.items():
            result[g] = v.get("type", "BLOCK") if isinstance(v, dict) else v
        return result
    if inp and all(isinstance(v, str) for v in inp.values()):
        return dict(inp)
    return {}


def analyse_session(log_path: Path) -> dict | None:
    log = json.loads(log_path.read_text())
    if "turns" not in log or not log["turns"]:
        return None

    meta = log.get("metadata", {})
    model = meta.get("model", log_path.stem.split("_seed")[0])
    seed = meta.get("seed")
    # n_genes added to metadata in PR #45; fall back to directory name for old logs
    n_genes = meta.get("n_genes") or int(log_path.parent.parent.name.lstrip("N"))
    budget_total = log.get("summary", {}).get("budget_total", 0)

    if budget_total == 0:
        return None

    type_counts: dict[str, int] = defaultdict(int)
    seen_genes: set[str] = set()
    redundant = 0
    total_gene_perturbations = 0
    first_prediction_exp_idx: int | None = None
    experiment_idx = 0

    for turn in log["turns"]:
        for tc in turn.get("tool_calls", []):
            tool = tc.get("tool", "")

            if tool == "run_experiment":
                interventions = _parse_interventions(tc.get("input", {}))
                for gene, iv_type in interventions.items():
                    type_counts[iv_type.upper()] += 1
                    if gene in seen_genes:
                        redundant += 1
                    seen_genes.add(gene)
                    total_gene_perturbations += 1
                experiment_idx += 1

            elif tool == "get_next_prediction_task" and first_prediction_exp_idx is None:
                first_prediction_exp_idx = experiment_idx

    if first_prediction_exp_idx is None:
        # Agent never called get_next_prediction_task — treat as full budget used
        first_prediction_exp_idx = experiment_idx

    total_iv = sum(type_counts.values()) or 1
    commitment = first_prediction_exp_idx / budget_total

    return {
        "model": model,
        "seed": seed,
        "n_genes": n_genes,
        "budget_total": budget_total,
        "commitment_fraction": round(commitment, 3),
        "block_fraction": round(type_counts["BLOCK"] / total_iv, 3),
        "boost_fraction": round(type_counts["BOOST"] / total_iv, 3),
        "dampen_fraction": round(type_counts["DAMPEN"] / total_iv, 3),
        "redundancy_fraction": round(redundant / total_gene_perturbations, 3)
            if total_gene_perturbations > 0 else 0.0,
        "n_experiments": experiment_idx,
        "stalled": any(t.get("stall") for t in log["turns"]),
    }


def _mean_std(values: list[float]) -> str:
    if not values:
        return "n/a"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{m:.3f}±{s:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="Filter to a specific model")
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
            r = analyse_session(log_file)
            if r is None:
                continue
            if args.model and r["model"] != args.model:
                continue
            records.append(r)

    if not records:
        print("No records parsed.")
        return

    # Group by model × n_genes
    from itertools import groupby
    models = sorted({r["model"] for r in records})
    n_values = sorted({r["n_genes"] for r in records if r["n_genes"] is not None})

    print(f"\nStrategy analysis — scaling study\n")

    for model in models:
        model_recs = [r for r in records if r["model"] == model]
        if not model_recs:
            continue
        print(f"{'─'*80}")
        print(f"Model: {model}")
        print(f"  {'N':>6}  {'Commit':>10}  {'BLOCK':>8}  {'BOOST':>8}  "
              f"{'DAMPEN':>8}  {'Redund':>8}  {'n':>4}")
        for n in n_values:
            recs = [r for r in model_recs if r["n_genes"] == n and not r["stalled"]]
            if not recs:
                print(f"  {n:>6}  {'—':>10}  {'—':>8}  {'—':>8}  {'—':>8}  {'—':>8}  {'—':>4}")
                continue
            print(
                f"  {n:>6}  "
                f"{_mean_std([r['commitment_fraction'] for r in recs]):>10}  "
                f"{_mean_std([r['block_fraction'] for r in recs]):>8}  "
                f"{_mean_std([r['boost_fraction'] for r in recs]):>8}  "
                f"{_mean_std([r['dampen_fraction'] for r in recs]):>8}  "
                f"{_mean_std([r['redundancy_fraction'] for r in recs]):>8}  "
                f"{len(recs):>4}"
            )
        print()

    # Save per-session records
    out_path = Path(__file__).parent / "strategy_analysis.jsonl"
    with open(out_path, "w") as f:
        for r in sorted(records, key=lambda x: (x["model"], x["n_genes"] or 0, x["seed"] or 0)):
            f.write(json.dumps(r) + "\n")
    print(f"Per-session records → {out_path}")


if __name__ == "__main__":
    main()
