"""
Gene coverage analysis for scaling study — post-hoc, no API calls needed.

Computes per-session gene coverage fraction (unique genes perturbed / total genes)
and aggregates by model × N. Answers whether Sonnet's scaling robustness is
explained by maintaining coverage as N grows.
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
    budget_total = log.get("summary", {}).get("budget_total", 0)
    if budget_total == 0:
        return None

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

    coverage = len(seen_genes) / n_genes

    return {
        "model": model,
        "seed": seed,
        "n_genes": n_genes,
        "budget_total": budget_total,
        "n_experiments": n_experiments,
        "budget_used_fraction": round(n_experiments / budget_total, 3),
        "unique_genes": len(seen_genes),
        "coverage_fraction": round(coverage, 3),
        "stalled": any(t.get("stall") for t in log["turns"]),
    }


def _mean_std(values: list[float]) -> str:
    if not values:
        return "n/a"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
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

    print(f"\nGene coverage analysis — scaling study\n")
    for model in models:
        model_recs = [r for r in records if r["model"] == model]
        print(f"{'─'*70}")
        print(f"Model: {model}")
        print(f"  {'N':>6}  {'Coverage':>12}  {'Unique genes':>14}  {'Budget used':>12}  {'n':>4}")
        for n in n_values:
            recs = [r for r in model_recs if r["n_genes"] == n and not r["stalled"]]
            if not recs:
                continue
            print(
                f"  {n:>6}  "
                f"{_mean_std([r['coverage_fraction'] for r in recs]):>12}  "
                f"{_mean_std([r['unique_genes'] for r in recs]):>14}  "
                f"{_mean_std([r['budget_used_fraction'] for r in recs]):>12}  "
                f"{len(recs):>4}"
            )
        print()

    out_path = Path(__file__).parent / "coverage_analysis.jsonl"
    with open(out_path, "w") as f:
        for r in sorted(records, key=lambda x: (x["model"], x["n_genes"] or 0, x["seed"] or 0)):
            f.write(json.dumps(r) + "\n")
    print(f"Per-session records → {out_path}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    main()
