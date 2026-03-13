"""
LEMONOIDS benchmark evaluation script.

Usage:
    # Run a single model on canonical seeds (0–19)
    python evaluate.py --model claude-opus-4-6

    # Compare multiple models
    python evaluate.py --model claude-opus-4-6 --model gpt-5.1

    # Heuristic agent (no API key required)
    python evaluate.py --heuristic

    # Disease mode
    python evaluate.py --model claude-opus-4-6 --disease

    # Difficulty tier (easy / medium / hard, or prokaryote / simple_eukaryote / complex_eukaryote)
    python evaluate.py --model claude-opus-4-6 --difficulty hard
    python evaluate.py --heuristic --difficulty easy

    # Custom seeds
    python evaluate.py --model claude-opus-4-6 --seeds 0 1 2 3 4
    python evaluate.py --model claude-opus-4-6 --seeds 0:10

    # Quick test
    python evaluate.py --model claude-opus-4-6 --n 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Canonical benchmark configuration
# ---------------------------------------------------------------------------

CANONICAL_SEEDS = list(range(20))
DEFAULT_N_GENES = 15
DEFAULT_N_MODULES = 4

# ---------------------------------------------------------------------------
# Heuristic agent (no API required)
# ---------------------------------------------------------------------------


def run_heuristic(session) -> dict[str, Any]:
    """
    Systematic heuristic agent: BLOCK all observable genes one by one,
    then make additive predictions. No API calls required.
    """
    from lemonoids.experiment import recommended_budget

    info = session.get_info()
    gene_names = info["gene_names"]
    baseline = info["baseline_phenotypes"]
    phenotype_labels = info["observable_phenotypes"]

    # Phase 1: BLOCK each gene and record phenotype shifts
    effects: dict[str, dict[str, float]] = {}
    for gene in gene_names:
        if session.budget_used >= session.budget - 2:
            break
        result = session.run_experiment({gene: {"type": "BLOCK"}})
        if "error" not in result:
            effects[gene] = {
                label: result["phenotypes"].get(label, baseline[label]) - baseline[label]
                for label in phenotype_labels
            }

    # Phase 2: submit predictions using additive model
    while True:
        task = session.get_next_prediction_task()
        if task.get("done"):
            break
        prediction: dict[str, float] = {}
        for label in phenotype_labels:
            pred = baseline[label]
            for gene, iv in task["interventions"].items():
                if gene in effects:
                    sign = -1.0 if iv.get("type") == "BLOCK" else 1.0
                    pred += sign * effects[gene].get(label, 0.0)
            prediction[label] = max(0.0, min(1.0, pred))
        session.submit_prediction(task["task_id"], prediction)

    # Disease mode: naive hypothesis + rescue attempt
    if session.is_disease:
        disease_info = session.get_info()
        aberrant = disease_info.get("aberrant_phenotypes", [])
        # Pick gene with largest effect on aberrant phenotypes as hypothesis
        best_gene = gene_names[0]
        best_score = -1.0
        for gene, eff in effects.items():
            score = sum(abs(eff.get(label, 0.0)) for label in aberrant)
            if score > best_score:
                best_score = score
                best_gene = gene
        session.submit_malfunction_hypothesis(best_gene, "LOCK_HI")
        session.test_rescue({best_gene: {"type": "BLOCK"}})

    session.submit_hypothesis("Heuristic systematic sweep — no causal model.")
    return session.get_summary()


# ---------------------------------------------------------------------------
# Seed parsing
# ---------------------------------------------------------------------------


def parse_seeds(seeds_args: list[str] | None, n: int) -> list[int]:
    """Parse --seeds arguments into a list of ints."""
    if not seeds_args:
        return CANONICAL_SEEDS[:n]
    seeds: list[int] = []
    for s in seeds_args:
        if ":" in s:
            parts = s.split(":")
            seeds.extend(range(int(parts[0]), int(parts[1])))
        else:
            seeds.append(int(s))
    return seeds


# ---------------------------------------------------------------------------
# Single model evaluation
# ---------------------------------------------------------------------------


def evaluate_model(
    model_name: str,
    seeds: list[int],
    disease: bool,
    difficulty: str,
    results_dir: Path,
    verbose: bool,
) -> list[dict[str, Any]]:
    """Run one model across all seeds. Returns list of per-organism records."""
    from lemonoids import (
        generate_organism, generate_disease_organism, ExperimentSession, run_agent
    )

    records: list[dict[str, Any]] = []

    for seed in seeds:
        print(f"  seed={seed} ... ", end="", flush=True)
        try:
            if disease:
                org = generate_disease_organism(seed=seed, difficulty=difficulty)
            else:
                org = generate_organism(seed=seed, difficulty=difficulty)
            session = ExperimentSession(org, seed=seed)

            log_path = str(results_dir / "logs" / f"{model_name}_seed{seed:04d}.json")

            if model_name == "heuristic":
                summary = run_heuristic(session)
            else:
                summary = run_agent(
                    session,
                    model=model_name,
                    verbose=verbose,
                    log_path=log_path,
                )

            record = _make_record(seed, org, summary, model_name, disease, difficulty)
            records.append(record)
            print(f"mse={record.get('avg_mse', 'n/a')}  acc={record.get('avg_accuracy', 'n/a')}")

        except Exception as e:
            print(f"ERROR: {e}")
            records.append({"seed": seed, "model": model_name, "error": str(e)})

    return records


def _composite_score(record: dict, disease: bool) -> float | None:
    """
    Composite benchmark score (0–1, higher is better).

    Healthy track:  accuracy
    Disease track:  mean(accuracy, diagnosis_score, rescue_fraction)

    Prediction accuracy is the shared component across both tracks.
    MSE is reported separately as a secondary metric.
    """
    acc = record.get("avg_accuracy")
    if acc is None:
        return None
    if not disease:
        return round(acc, 4)
    diag = record.get("diagnosis_score")
    rescue = record.get("rescue_fraction")
    components = [v for v in [acc, diag, rescue] if v is not None]
    return round(sum(components) / len(components), 4) if components else None


def _make_record(seed, org, summary, model_name, disease, difficulty) -> dict[str, Any]:
    record: dict[str, Any] = {
        "seed": seed,
        "model": model_name,
        "difficulty": difficulty,
        "n_genes": len(org.genes),
        "n_modules": len(org.modules),
        "disease": disease,
        "avg_mse": summary.get("avg_mse"),
        "avg_accuracy": summary.get("avg_accuracy"),
        "budget_used": summary.get("budget_used"),
        "budget_total": summary.get("budget_total"),
    }
    if disease:
        hyp = summary.get("malfunction_hypothesis") or {}
        rescue_results = summary.get("rescue_results") or []
        best_rescue = max(
            (r.get("restored_fraction", 0.0) for r in rescue_results), default=None
        )
        record["diagnosis_score"] = hyp.get("score")
        record["rescue_fraction"] = best_rescue
    record["composite_score"] = _composite_score(record, disease)
    return record


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


def print_summary(model_name: str, records: list[dict], disease: bool) -> None:
    valid = [r for r in records if "error" not in r]
    n = len(valid)
    if n == 0:
        print(f"\n[{model_name}] No valid results.")
        return

    def mean_std(key):
        vals = [r[key] for r in valid if r.get(key) is not None]
        if not vals:
            return "n/a"
        mu = sum(vals) / len(vals)
        std = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
        return f"{mu:.3f} ± {std:.3f}"

    budget_pcts = [
        r["budget_used"] / r["budget_total"]
        for r in valid
        if r.get("budget_used") and r.get("budget_total")
    ]
    budget_str = f"{sum(budget_pcts)/len(budget_pcts)*100:.0f}%" if budget_pcts else "n/a"

    width = 50
    print(f"\n{'─' * width}")
    difficulties = list({r.get("difficulty", "medium") for r in valid})
    diff_str = difficulties[0] if len(difficulties) == 1 else "/".join(sorted(difficulties))
    print(f"  Model: {model_name}  |  N={n}  |  difficulty={diff_str}  |  mode={'disease' if disease else 'healthy'}")
    print(f"{'─' * width}")
    print(f"  ★ Composite score     {mean_std('composite_score')}")
    print(f"{'─' * width}")
    print(f"  Prediction MSE       {mean_std('avg_mse')}")
    print(f"  Prediction accuracy  {mean_std('avg_accuracy')}")
    if disease:
        print(f"  Diagnosis score      {mean_std('diagnosis_score')}")
        print(f"  Rescue fraction      {mean_std('rescue_fraction')}")
    print(f"  Budget used          {budget_str}")
    print(f"{'─' * width}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LEMONOIDS benchmark evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model", action="append", dest="models", metavar="MODEL",
        help="Model to evaluate (repeatable). E.g. claude-opus-4-6, gpt-5.1",
    )
    parser.add_argument(
        "--heuristic", action="store_true",
        help="Include the heuristic baseline: BLOCKs each gene once, then predicts additively. No API key required.",
    )
    parser.add_argument(
        "--disease", action="store_true",
        help="Evaluate in disease mode (default: healthy)",
    )
    parser.add_argument(
        "--difficulty", default="medium",
        metavar="TIER",
        help=(
            "Organism difficulty tier (default: medium). "
            "Accepts: easy / medium / hard  or  "
            "prokaryote / simple_eukaryote / complex_eukaryote"
        ),
    )
    parser.add_argument(
        "--n", type=int, default=20,
        help="Number of organisms to evaluate (default: 20, uses canonical seeds 0..N-1)",
    )
    parser.add_argument(
        "--seeds", nargs="+", metavar="SEED",
        help="Override canonical seeds. Integers or range (e.g. 0:10 or 0 1 2 3)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print per-turn agent output",
    )
    parser.add_argument(
        "--out", default="results", metavar="DIR",
        help="Output directory for results (default: results/)",
    )
    args = parser.parse_args()

    models: list[str] = list(args.models or [])
    if args.heuristic:
        models.append("heuristic")

    if not models:
        parser.error("Specify at least one --model or use --heuristic")

    seeds = parse_seeds(args.seeds, args.n)
    print(f"Evaluating {len(models)} model(s) on {len(seeds)} organisms "
          f"(seeds {seeds[0]}..{seeds[-1]}, "
          f"difficulty={args.difficulty}, "
          f"mode={'disease' if args.disease else 'healthy'})")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(args.out) / timestamp
    (results_dir / "logs").mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []

    for model_name in models:
        if model_name == "heuristic":
            print(f"\n[heuristic]  (systematic baseline: BLOCK each gene once, predict additively — no LLM)")
        else:
            print(f"\n[{model_name}]")
        records = evaluate_model(model_name, seeds, args.disease, args.difficulty, results_dir, args.verbose)
        all_records.extend(records)
        print_summary(model_name, records, args.disease)

        # Save per-model JSONL
        model_file = results_dir / f"{model_name.replace('/', '_')}.jsonl"
        with open(model_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    # Save combined results
    combined_file = results_dir / "results.jsonl"
    with open(combined_file, "w") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults saved → {results_dir}/")


if __name__ == "__main__":
    main()
