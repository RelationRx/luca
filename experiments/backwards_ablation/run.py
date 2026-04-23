"""
Backwards-organism ablation runner.

Runs the LUCA benchmark on backwards-inverted organisms (every signed quantity
flipped: GRN edge weights, gene biases, signal modes, phenotype readout
weights). Paired with the paper's existing forward results to test whether
top-LLM performance reflects genuine causal inference or transferred
structural priors.

Grid: mode (healthy, disease) — both medium tier. Backwards-only: forward
scores are already in experiments/paper_v1/ and are joined in downstream
analysis (experiments/backwards_ablation/analyze.py, PR 3).

Seeds are read from valid_seeds.json produced by prescreen.py.

Usage
-----
# Pre-screen (writes valid_seeds.json — no API cost):
python experiments/backwards_ablation/prescreen.py

# Smoke — heuristic only (no API cost):
python experiments/backwards_ablation/run.py --model heuristic

# Full sweep — Opus + DeepSeek + GPT-4o on both modes:
python experiments/backwards_ablation/run.py \\
    --model claude-opus-4-6 --model deepseek-v3 --model gpt-4o

# Single model × single mode:
python experiments/backwards_ablation/run.py --model claude-sonnet-4-6 --mode healthy

Results
-------
experiments/backwards_ablation/results/<mode>/<model>.jsonl
experiments/backwards_ablation/logs/<mode>/                 (gitignored)
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

from evaluate import evaluate_model, print_summary  # noqa: E402

_write_lock = threading.Lock()

ABLATION_DIR = Path(__file__).parent
VALID_SEEDS_PATH = ABLATION_DIR / "valid_seeds.json"

MODES = ("healthy", "disease")
DIFFICULTY = "medium"  # spec §2.2 — medium only


def _load_valid_seeds(mode: str, difficulty: str = DIFFICULTY) -> list[int]:
    if not VALID_SEEDS_PATH.exists():
        raise FileNotFoundError(
            f"{VALID_SEEDS_PATH} does not exist. Run prescreen.py first:\n"
            f"  python {ABLATION_DIR.relative_to(REPO_ROOT)}/prescreen.py"
        )
    manifest = json.loads(VALID_SEEDS_PATH.read_text())
    cell_key = f"{difficulty}_{mode}"
    if cell_key not in manifest:
        raise KeyError(
            f"valid_seeds.json has no cell {cell_key!r}. "
            f"Found cells: {list(manifest.keys())}"
        )
    return list(manifest[cell_key]["seeds"])


def _run_one_model(
    model_name: str,
    mode: str,
    seeds: list[int],
    verbose: bool,
    max_tokens_per_turn: int | None,
) -> tuple[str, list[dict]]:
    results_dir = ABLATION_DIR / "results" / mode
    logs_dir = ABLATION_DIR / "logs" / mode
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[{mode} | {model_name}] {len(seeds)} seeds")
    records = evaluate_model(
        model_name=model_name,
        seeds=seeds,
        disease=(mode == "disease"),
        difficulty=DIFFICULTY,
        results_dir=logs_dir,
        verbose=verbose,
        active_tasks=frozenset({"predict", "diagnose", "rescue"}),
        max_tokens_per_turn=max_tokens_per_turn,
        backwards=True,
    )
    print_summary(model_name, records, disease=(mode == "disease"))

    model_file = results_dir / f"{model_name.replace('/', '_')}.jsonl"
    with _write_lock:
        with open(model_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    return model_name, records


def run_sweep(
    mode: str,
    models: list[str],
    n: int | None,
    seeds_override: list[int] | None,
    parallel: bool,
    verbose: bool,
    max_tokens_per_turn: int | None,
) -> None:
    if seeds_override is not None:
        seeds = seeds_override
    else:
        valid = _load_valid_seeds(mode)
        seeds = valid[:n] if n else valid

    print(f"\n{'=' * 60}")
    print(
        f"Sweep: backwards {mode}  |  "
        f"seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)})  |  "
        f"models: {models}"
    )
    print(f"{'=' * 60}")

    if parallel and len(models) > 1:
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(
                    _run_one_model, m, mode, seeds, verbose, max_tokens_per_turn,
                ): m
                for m in models
            }
            for future in as_completed(futures):
                future.result()
    else:
        for m in models:
            _run_one_model(m, mode, seeds, verbose, max_tokens_per_turn)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backwards-organism ablation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model", action="append", dest="models", metavar="MODEL", required=True,
        help="Model(s) to run. Repeatable. Required — no default to prevent accidental spend.",
    )
    parser.add_argument(
        "--mode", action="append", dest="modes", choices=list(MODES),
        help=f"Mode(s). Repeatable. Default: both ({list(MODES)}).",
    )
    parser.add_argument(
        "--n", type=int, default=None,
        help="Number of seeds to run (default: all valid seeds from valid_seeds.json).",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, metavar="SEED",
        help="Explicit seed list (bypasses valid_seeds.json).",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--no-parallel", action="store_true",
        help="Run models sequentially instead of in parallel.",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=None, metavar="N",
        help="Per-turn token cap (for API rate-limited models).",
    )
    args = parser.parse_args()

    modes = args.modes or list(MODES)
    parallel = not args.no_parallel

    for mode in modes:
        run_sweep(
            mode=mode,
            models=args.models,
            n=args.n,
            seeds_override=args.seeds,
            parallel=parallel,
            verbose=args.verbose,
            max_tokens_per_turn=args.max_tokens,
        )


if __name__ == "__main__":
    main()
