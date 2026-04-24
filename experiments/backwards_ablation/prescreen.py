"""
Backwards-organism seed pre-screen.

For each canonical seed × {medium healthy, medium disease}, attempt to generate
the backwards organism and record whether it succeeds. Organisms that fail —
typically because no rescuable malfunction is found under backwards dynamics
in disease mode, or (rarely) because the simulator fails to converge — are
excluded from the downstream LLM sweep.

Output
------
experiments/backwards_ablation/valid_seeds.json — the subset that succeeds,
    per (tier, mode) cell. The run.py sweep reads this file and only evaluates
    LLMs on the surviving seeds.

Usage
-----
python experiments/backwards_ablation/prescreen.py
python experiments/backwards_ablation/prescreen.py --difficulty medium --mode disease
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from luca import generate_organism, generate_disease_organism  # noqa: E402

CANONICAL_SEEDS = list(range(20))
ABLATION_DIR = Path(__file__).parent

# Cells: (difficulty, mode) tuples that the sweep runs on. Medium only per the
# design spec §2.2; hard and easy are out of scope.
DEFAULT_CELLS = [
    ("medium", "healthy"),
    ("medium", "disease"),
]


def _attempt(seed: int, difficulty: str, mode: str) -> dict:
    """Attempt backwards generation for one (seed, tier, mode). Returns a record
    with {"seed": int, "ok": bool, "error": str | None}."""
    try:
        if mode == "healthy":
            generate_organism(seed=seed, difficulty=difficulty, backwards=True)
        else:
            generate_disease_organism(seed=seed, difficulty=difficulty, backwards=True)
        return {"seed": seed, "ok": True, "error": None}
    except Exception as e:
        return {"seed": seed, "ok": False, "error": f"{type(e).__name__}: {e}"}


def prescreen(difficulties: list[str], modes: list[str], seeds: list[int]) -> dict:
    """Run pre-screen across the requested cells. Returns dict keyed by
    '<difficulty>_<mode>' with {'seeds': [valid ids], 'failures': [records]}.
    """
    out: dict[str, dict] = {}
    for difficulty in difficulties:
        for mode in modes:
            cell_key = f"{difficulty}_{mode}"
            print(f"\n[{cell_key}] screening {len(seeds)} seeds …")
            records = [_attempt(s, difficulty, mode) for s in seeds]
            valid = [r["seed"] for r in records if r["ok"]]
            failures = [r for r in records if not r["ok"]]
            print(f"  valid: {len(valid)}/{len(seeds)}")
            for f in failures:
                print(f"    seed={f['seed']:3d}  error: {f['error']}")
            out[cell_key] = {"seeds": valid, "failures": failures}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--difficulty", action="append", choices=["medium"],
        help="Difficulty tier(s). Default: medium.",
    )
    parser.add_argument(
        "--mode", action="append", choices=["healthy", "disease"],
        help="Mode(s). Default: both.",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, default=None,
        help="Override canonical seeds 0-19.",
    )
    parser.add_argument(
        "--out", type=Path, default=ABLATION_DIR / "valid_seeds.json",
        help="Output JSON path.",
    )
    args = parser.parse_args()

    difficulties = args.difficulty or ["medium"]
    modes = args.mode or ["healthy", "disease"]
    seeds = args.seeds or CANONICAL_SEEDS

    result = prescreen(difficulties, modes, seeds)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nValid seeds manifest → {args.out}")

    # Fail-fast if any cell is below the ≥15/20 escalation threshold from the spec.
    for cell_key, cell in result.items():
        n_valid = len(cell["seeds"])
        if n_valid < 15:
            print(
                f"\nWARNING: {cell_key} has only {n_valid}/20 valid seeds. "
                "Per spec §6, this is below the escalation threshold. "
                "Consider pausing the sweep and reviewing the inversion policy.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
