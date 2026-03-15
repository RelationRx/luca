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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Make sure repo root is on the path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from experiments.paper_v1.config import MODELS, SEEDS, SWEEPS

# Import evaluate helpers directly — avoids subprocess overhead and keeps logs tidy
from evaluate import evaluate_model, print_summary, run_heuristic, parse_seeds   # noqa: E402


_write_lock = threading.Lock()


def _run_one_model(
    model_name: str,
    seeds: list[int],
    disease: bool,
    difficulty: str,
    results_dir: Path,
    logs_dir: Path,
    verbose: bool,
) -> tuple[str, list[dict]]:
    """Run a single model and save its JSONL. Returns (model_name, records)."""
    print(f"\n[{model_name}]")
    records = evaluate_model(
        model_name=model_name,
        seeds=seeds,
        disease=disease,
        difficulty=difficulty,
        results_dir=logs_dir,
        verbose=verbose,
        active_tasks=None,
    )
    print_summary(model_name, records, disease)

    # Merge with any existing records (e.g. from a partial run) — lock for thread safety
    model_file = results_dir / f"{model_name.replace('/', '_')}.jsonl"
    with _write_lock:
        if model_file.exists():
            existing = [json.loads(l) for l in model_file.read_text().splitlines() if l.strip()]
            new_seeds = {r["seed"] for r in records}
            merged = [r for r in existing if r["seed"] not in new_seeds] + records
            records = sorted(merged, key=lambda r: r["seed"])
        with open(model_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    return model_name, records


def run_sweep(
    sweep_name: str,
    models: list[str],
    n: int | None = None,
    seeds_override: list[int] | None = None,
    parallel: bool = True,
    verbose: bool = False,
) -> None:
    cfg = SWEEPS[sweep_name]
    seeds = seeds_override if seeds_override is not None else (SEEDS[:n] if n else SEEDS)
    difficulty = cfg["difficulty"]
    disease = cfg["disease"]

    results_dir = Path(__file__).parent / "results" / sweep_name
    logs_dir = Path(__file__).parent / "logs" / sweep_name
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Sweep: {sweep_name}  |  difficulty={difficulty}  |  disease={disease}")
    print(f"Seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)} total)  |  models: {models}  |  parallel={parallel}")
    print(f"{'='*60}")

    all_records: list[dict] = []

    if parallel and len(models) > 1:
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(_run_one_model, m, seeds, disease, difficulty, results_dir, logs_dir, verbose): m
                for m in models
            }
            for future in as_completed(futures):
                _, records = future.result()
                all_records.extend(records)
    else:
        for model_name in models:
            _, records = _run_one_model(model_name, seeds, disease, difficulty, results_dir, logs_dir, verbose)
            all_records.extend(records)

    # Rewrite concatenated results
    all_file = results_dir / "all.jsonl"
    with open(all_file, "w") as f:
        for r in sorted(all_records, key=lambda r: (r["model"], r["seed"])):
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
    parser.add_argument(
        "--seeds", nargs="+", metavar="SEED",
        help="Override seeds. Integers or range e.g. 10:20 or 0 1 2 3. Default: all 20.",
    )
    parser.add_argument(
        "--no-parallel", action="store_true",
        help="Run models sequentially instead of in parallel (default: parallel).",
    )
    args = parser.parse_args()

    models = args.models or ["heuristic"]
    sweeps = args.sweeps or list(SWEEPS.keys())
    seeds_override = parse_seeds(args.seeds, 20) if args.seeds else None
    parallel = not args.no_parallel

    for sweep_name in sweeps:
        run_sweep(sweep_name, models, n=args.n, seeds_override=seeds_override, parallel=parallel, verbose=args.verbose)


if __name__ == "__main__":
    main()
