"""
Real-vocabulary ablation runner.

Runs the same organisms with invented vs real gene names to test whether
vocabulary affects LLM prediction performance. Paired comparison per seed:
same topology, same model, only the gene name strings differ.

Difficulty × vocabulary grid:
  medium_invented  medium_real
  hard_invented    hard_real

Seeds reuse the pre-screened medium/hard seeds from paper_v1
(experiments/paper_v1/selected_seeds.json) so results can be compared
directly against the paper_v1 healthy-mode tables.

Usage
-----
# Phase 1 from the design spec: Opus + DeepSeek on both tiers
python experiments/vocabulary_ablation/run.py \\
    --model claude-opus-4-6 --model deepseek-v3

# Single tier, single vocabulary (smoke)
python experiments/vocabulary_ablation/run.py \\
    --model claude-opus-4-6 \\
    --difficulty medium --vocabulary invented --n 3

# Phase 2: add more models
python experiments/vocabulary_ablation/run.py \\
    --model claude-sonnet-4-6 --model gpt-5.1

Results
-------
experiments/vocabulary_ablation/results/<difficulty>_<vocabulary>/<model>.jsonl
experiments/vocabulary_ablation/logs/<difficulty>_<vocabulary>/                 (gitignored)
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

from evaluate import evaluate_model, print_summary, parse_seeds  # noqa: E402

_write_lock = threading.Lock()

SWEEP_DIR = Path(__file__).parent

DIFFICULTIES = ("medium", "hard")
VOCABULARIES = ("invented", "real")
PROMPT_VARIANTS = ("suppress", "permit")

_seeds_path = REPO_ROOT / "experiments" / "paper_v1" / "selected_seeds.json"
_SELECTED = json.loads(_seeds_path.read_text())["seeds"]


def _seeds_for(difficulty: str) -> list[int]:
    return list(_SELECTED[difficulty])


def _sweep_name(difficulty: str, vocabulary: str, prompt_variant: str) -> str:
    """Name results/logs directory for this cell of the experimental grid.

    "suppress" (the benchmark default) is left implicit so the existing
    Phase 1 directories remain unchanged; non-default variants get a suffix.
    """
    base = f"{difficulty}_{vocabulary}"
    return base if prompt_variant == "suppress" else f"{base}_{prompt_variant}"


def _run_one_model(
    model_name: str,
    difficulty: str,
    vocabulary: str,
    prompt_variant: str,
    seeds: list[int],
    verbose: bool,
    max_tokens_per_turn: int | None,
) -> tuple[str, list[dict]]:
    sweep = _sweep_name(difficulty, vocabulary, prompt_variant)
    results_dir = SWEEP_DIR / "results" / sweep
    logs_dir = SWEEP_DIR / "logs" / sweep
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[{sweep} | {model_name}]")
    records = evaluate_model(
        model_name=model_name,
        seeds=seeds,
        disease=False,
        difficulty=difficulty,
        results_dir=logs_dir,
        verbose=verbose,
        active_tasks=frozenset({"predict", "diagnose", "rescue"}),
        max_tokens_per_turn=max_tokens_per_turn,
        vocabulary=vocabulary,
        system_prompt_variant=prompt_variant,
    )
    print_summary(model_name, records, disease=False)

    model_file = results_dir / f"{model_name.replace('/', '_')}.jsonl"
    with _write_lock:
        with open(model_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    return model_name, records


def run_sweep(
    difficulty: str,
    vocabulary: str,
    prompt_variant: str,
    models: list[str],
    n: int | None,
    seeds_override: list[int] | None,
    parallel: bool,
    verbose: bool,
    max_tokens_per_turn: int | None,
) -> None:
    default_seeds = _seeds_for(difficulty)
    seeds = seeds_override if seeds_override is not None else (default_seeds[:n] if n else default_seeds)
    sweep = _sweep_name(difficulty, vocabulary, prompt_variant)

    print(f"\n{'=' * 60}")
    print(f"Sweep: {sweep}  |  seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)})  |  models: {models}")
    print(f"{'=' * 60}")

    if parallel and len(models) > 1:
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(_run_one_model, m, difficulty, vocabulary, prompt_variant, seeds, verbose, max_tokens_per_turn): m
                for m in models
            }
            for future in as_completed(futures):
                future.result()
    else:
        for m in models:
            _run_one_model(m, difficulty, vocabulary, prompt_variant, seeds, verbose, max_tokens_per_turn)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real-vocabulary ablation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model", action="append", dest="models", metavar="MODEL", required=True,
        help="Model(s) to run. Repeatable. Required — no default to prevent accidental spend.",
    )
    parser.add_argument(
        "--difficulty", action="append", dest="difficulties", choices=list(DIFFICULTIES),
        help=f"Difficulty tier(s). Repeatable. Default: both ({list(DIFFICULTIES)}).",
    )
    parser.add_argument(
        "--vocabulary", action="append", dest="vocabularies", choices=list(VOCABULARIES),
        help=f"Vocabulary(s). Repeatable. Default: both ({list(VOCABULARIES)}).",
    )
    parser.add_argument(
        "--system-prompt-variant", action="append", dest="prompt_variants",
        choices=list(PROMPT_VARIANTS),
        help=(
            "System prompt variant(s). Repeatable. "
            "'suppress' = benchmark default ('biological knowledge is IRRELEVANT'). "
            "'permit'   = 'you may use biological knowledge freely'. "
            "Default: ['suppress'] only (matches Phase 1)."
        ),
    )
    parser.add_argument("--n", type=int, default=None, help="Number of seeds (default: all 20).")
    parser.add_argument("--seeds", nargs="+", metavar="SEED", help="Explicit seed list or range (e.g. 0:5).")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-parallel", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=None, metavar="N")
    args = parser.parse_args()

    difficulties = args.difficulties or list(DIFFICULTIES)
    vocabularies = args.vocabularies or list(VOCABULARIES)
    prompt_variants = args.prompt_variants or ["suppress"]
    parallel = not args.no_parallel
    seeds_override = (
        parse_seeds(args.seeds, max(len(_seeds_for(d)) for d in difficulties))
        if args.seeds else None
    )

    for prompt_variant in prompt_variants:
        for difficulty in difficulties:
            for vocabulary in vocabularies:
                run_sweep(
                    difficulty, vocabulary, prompt_variant, args.models,
                    n=args.n, seeds_override=seeds_override,
                    parallel=parallel, verbose=args.verbose,
                    max_tokens_per_turn=args.max_tokens,
                )


if __name__ == "__main__":
    main()
