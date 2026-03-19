"""
Scaling study v1 — network size sweep runner.

Usage
-----
# Smoke test: heuristic on N=20 and N=40, 3 seeds each
python experiments/scaling_v1/run.py --model heuristic --n 3

# Core sweep (all N values, core models)
python experiments/scaling_v1/run.py --model claude-sonnet-4-6 --model heuristic --model random

# Single N value
python experiments/scaling_v1/run.py --n-genes 80 --model claude-sonnet-4-6

# Extended models at large N (after core results are in)
python experiments/scaling_v1/run.py --n-genes 80 --n-genes 160 \\
    --model claude-opus-4-6 --model gpt-4o

Results
-------
experiments/scaling_v1/results/N<nnn>/<model>.jsonl   one record per seed
experiments/scaling_v1/logs/N<nnn>/                   per-session traces (gitignored)
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from experiments.scaling_v1.config import SWEEPS
from evaluate import evaluate_model, print_summary, parse_seeds

_write_lock = threading.Lock()


def _max_turns(n_genes: int) -> int:
    """Scale turn limit with network size: 50 base + N/4 extra turns."""
    return 50 + n_genes // 4


def _run_one_model(
    model_name: str,
    sweep_name: str,
    cfg: dict,
    seeds: list[int],
    results_dir: Path,
    logs_dir: Path,
    verbose: bool,
    max_tokens_per_turn: int | None = None,
) -> tuple[str, list[dict]]:
    print(f"\n[{model_name}]")
    records = evaluate_model(
        model_name=model_name,
        seeds=seeds,
        disease=cfg["disease"],
        difficulty=cfg["difficulty"],
        results_dir=logs_dir,
        verbose=verbose,
        active_tasks=frozenset({"predict"}),
        max_tokens_per_turn=max_tokens_per_turn,
        n_genes=cfg["n_genes"],
        max_turns=_max_turns(cfg["n_genes"]),
    )
    print_summary(model_name, records, cfg["disease"])

    model_file = results_dir / f"{model_name.replace('/', '_')}.jsonl"
    with _write_lock:
        with open(model_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    return model_name, records


def run_sweep(
    sweep_name: str,
    models: list[str],
    n: int | None = None,
    parallel: bool = True,
    verbose: bool = False,
    max_tokens_per_turn: int | None = None,
) -> None:
    cfg = SWEEPS[sweep_name]
    seeds = cfg["seeds"][:n] if n else cfg["seeds"]

    results_dir = Path(__file__).parent / "results" / sweep_name
    logs_dir = Path(__file__).parent / "logs" / sweep_name
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Sweep: {sweep_name}  |  n_genes={cfg['n_genes']}  |  difficulty={cfg['difficulty']}")
    print(f"Seeds: {seeds}  |  models: {models}  |  parallel={parallel}")
    print(f"max_turns={_max_turns(cfg['n_genes'])}")
    print(f"{'='*60}")

    all_records: list[dict] = []

    if parallel and len(models) > 1:
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(
                    _run_one_model, m, sweep_name, cfg, seeds,
                    results_dir, logs_dir, verbose, max_tokens_per_turn,
                ): m
                for m in models
            }
            for future in as_completed(futures):
                _, records = future.result()
                all_records.extend(records)
    else:
        for m in models:
            _, records = _run_one_model(
                m, sweep_name, cfg, seeds, results_dir, logs_dir, verbose, max_tokens_per_turn,
            )
            all_records.extend(records)

    all_file = results_dir / "all.jsonl"
    with open(all_file, "w") as f:
        for r in sorted(all_records, key=lambda r: (r["model"], r["seed"])):
            f.write(json.dumps(r) + "\n")

    print(f"\nResults → {results_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaling study v1 runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model", action="append", dest="models", metavar="MODEL",
        help="Model(s) to run. Repeatable.",
    )
    parser.add_argument(
        "--n-genes", action="append", dest="n_genes_list", type=int, metavar="N",
        help="Network size(s) to run. Repeatable. Default: all sizes in config.",
    )
    parser.add_argument(
        "--n", type=int, default=None, metavar="N",
        help="Number of seeds (default: all). Use --n 3 for a smoke test.",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-parallel", action="store_true")
    parser.add_argument(
        "--max-tokens", type=int, default=None, metavar="N",
        help="Cap max_tokens per turn for OpenAI models.",
    )
    args = parser.parse_args()

    # Resolve sweeps by n_genes
    if args.n_genes_list:
        sweep_names = [f"N{n:03d}" for n in args.n_genes_list]
        missing = [s for s in sweep_names if s not in SWEEPS]
        if missing:
            parser.error(f"Unknown N values: {missing}. Available: {list(SWEEPS.keys())}")
    else:
        sweep_names = list(SWEEPS.keys())

    for sweep_name in sweep_names:
        cfg_models = SWEEPS[sweep_name]["models"]
        models = args.models if args.models else cfg_models
        run_sweep(
            sweep_name, models,
            n=args.n,
            parallel=not args.no_parallel,
            verbose=args.verbose,
            max_tokens_per_turn=args.max_tokens,
        )


if __name__ == "__main__":
    main()
