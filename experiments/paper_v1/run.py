"""
Paper v1 experiment runner.

Usage
-----
# Run heuristic on all sweeps (free, validates setup)
python experiments/paper_v1/run.py --model heuristic

# Run a single model on one sweep
python experiments/paper_v1/run.py --model claude-sonnet-4-6 --sweep A_medium_healthy

# Run all models on all sweeps (full paper run)
python experiments/paper_v1/run.py --model claude-sonnet-4-6 --model claude-opus-4-6 \\
    --model gpt-4o --model gpt-4.1 --model gpt-5.1 --model heuristic

# Quick smoke test: 3 seeds only
python experiments/paper_v1/run.py --model claude-sonnet-4-6 --sweep A_medium_healthy --n 3

Results
-------
experiments/paper_v1/results/<sweep>/<model>.jsonl   one record per seed
experiments/paper_v1/results/<sweep>/all.jsonl        concatenation for analysis
experiments/paper_v1/logs/<sweep>/<model>_seed*.json  per-session agent traces (gitignored)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sure repo root is on the path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from experiments.paper_v1.config import MODELS, SEEDS, SWEEPS

# Import evaluate helpers directly — avoids subprocess overhead and keeps logs tidy
from evaluate import evaluate_model, print_summary, run_heuristic   # noqa: E402


def run_sweep(
    sweep_name: str,
    models: list[str],
    n: int | None = None,
    verbose: bool = False,
) -> None:
    cfg = SWEEPS[sweep_name]
    seeds = SEEDS[:n] if n else SEEDS
    difficulty = cfg["difficulty"]
    disease = cfg["disease"]

    results_dir = Path(__file__).parent / "results" / sweep_name
    logs_dir = Path(__file__).parent / "logs" / sweep_name
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Sweep: {sweep_name}  |  difficulty={difficulty}  |  disease={disease}")
    print(f"Seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)} total)  |  models: {models}")
    print(f"{'='*60}")

    all_records: list[dict] = []

    for model_name in models:
        print(f"\n[{model_name}]")
        records = evaluate_model(
            model_name=model_name,
            seeds=seeds,
            disease=disease,
            difficulty=difficulty,
            results_dir=logs_dir,
            verbose=verbose,
            active_tasks=None,  # all tasks
        )
        all_records.extend(records)
        print_summary(model_name, records, disease)

        # Save per-model JSONL
        model_file = results_dir / f"{model_name.replace('/', '_')}.jsonl"
        with open(model_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    # Write / append concatenated results for easy cross-model analysis
    all_file = results_dir / "all.jsonl"
    with open(all_file, "w") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults → {results_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paper v1 experiment runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model", action="append", dest="models", metavar="MODEL",
        help="Model(s) to run. Repeatable. Use 'heuristic' for the free baseline.",
    )
    parser.add_argument(
        "--sweep", action="append", dest="sweeps", metavar="SWEEP",
        choices=list(SWEEPS.keys()),
        help=(
            f"Sweep(s) to run. Repeatable. Choices: {list(SWEEPS.keys())}. "
            "Default: all sweeps."
        ),
    )
    parser.add_argument(
        "--n", type=int, default=None, metavar="N",
        help="Number of seeds (default: all 20). Use --n 3 for a quick smoke test.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print per-turn agent output.",
    )
    args = parser.parse_args()

    models = args.models or ["heuristic"]
    sweeps = args.sweeps or list(SWEEPS.keys())

    for sweep_name in sweeps:
        run_sweep(sweep_name, models, n=args.n, verbose=args.verbose)


if __name__ == "__main__":
    main()
