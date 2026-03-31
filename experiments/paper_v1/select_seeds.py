"""
Seed selection for the canonical benchmark.

Iterates seeds in order, runs full verification on each, and collects the
first TARGET_SEEDS passing seeds per tier. For medium difficulty, also
pre-screens disease stability (can a detectable malfunction be generated?).

Stops at MAX_SEEDS_TO_TRY if TARGET_SEEDS valid seeds are not found.

Output
------
- Terminal summary table
- experiments/paper_v1/selected_seeds.json  — selected seed lists per tier/mode

Usage
-----
    python experiments/paper_v1/select_seeds.py
    python experiments/paper_v1/select_seeds.py --target 20
    python experiments/paper_v1/select_seeds.py --difficulty medium
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lemonoids import generate_organism, generate_disease_organism, ExperimentSession  # noqa: E402
from lemonoids.dynamics import simulate_sigmoid, compute_phenotypes                    # noqa: E402
from lemonoids.generation import DIFFICULTY_PRESETS                                    # noqa: E402
from verify_organisms import verify_organism                                            # noqa: E402

TARGET_SEEDS = 10
MAX_SEEDS_TO_TRY = 60
DISEASE_TIERS = {"medium"}   # tiers that also need disease pre-screening


# ---------------------------------------------------------------------------
# Disease stability check
# ---------------------------------------------------------------------------

def check_disease_viable(seed: int, difficulty: str) -> tuple[bool, str]:
    """
    Try to generate a disease organism. Returns (viable, reason).
    Viable = generate_disease_organism succeeds without RuntimeError.
    """
    try:
        generate_disease_organism(seed=seed, difficulty=difficulty)
        return True, "ok"
    except RuntimeError as e:
        return False, f"disease_generation_failed: {e}"
    except Exception as e:
        return False, f"error: {e}"


# ---------------------------------------------------------------------------
# Per-seed selection logic
# ---------------------------------------------------------------------------

def evaluate_seed(seed: int, difficulty: str) -> dict:
    """
    Full evaluation of one seed. Returns a dict with:
      - healthy_pass: bool
      - disease_viable: bool | None  (None if not checked)
      - flags: list[str]
      - reason: str  (human-readable summary)
    """
    v = verify_organism(seed, difficulty)

    if "error" in v:
        return {
            "seed": seed, "difficulty": difficulty,
            "healthy_pass": False, "disease_viable": None,
            "flags": ["VERIFY_ERROR"], "reason": v["error"],
            "verification": v,
        }

    healthy_pass = v["pass"]
    flags = list(v["flags"])

    disease_viable = None
    if difficulty in DISEASE_TIERS and healthy_pass:
        viable, reason = check_disease_viable(seed, difficulty)
        disease_viable = viable
        if not viable:
            flags.append("DISEASE_UNSTABLE")

    reasons = []
    if not healthy_pass:
        reasons.append(f"healthy flags: {', '.join(v['flags'])}")
    if disease_viable is False:
        reasons.append("disease generation failed")
    reason = "; ".join(reasons) if reasons else "ok"

    return {
        "seed": seed,
        "difficulty": difficulty,
        "healthy_pass": healthy_pass,
        "disease_viable": disease_viable,
        "flags": flags,
        "reason": reason,
        "verification": v,
    }


def is_selected(result: dict, difficulty: str) -> bool:
    """A seed is selected if it passes healthy verification and disease check (if applicable)."""
    if not result["healthy_pass"]:
        return False
    if difficulty in DISEASE_TIERS and result["disease_viable"] is False:
        return False
    return True


# ---------------------------------------------------------------------------
# Main selection loop
# ---------------------------------------------------------------------------

def select_seeds(difficulty: str, target: int, max_try: int) -> dict:
    """
    Iterate seeds 0..max_try-1 until `target` valid seeds are found.
    Returns a results dict with selected seeds and per-seed details.
    """
    selected: list[int] = []
    rejected: list[dict] = []
    all_results: list[dict] = []

    print(f"\n{'='*62}")
    print(f"  {difficulty.upper()}  (target={target}, max_try={max_try})")
    print(f"{'='*62}")
    header = f"  {'Seed':>4}  {'Healthy':>8}  {'Disease':>8}  {'Result':>8}  Flags"
    print(header)
    print(f"  {'-'*58}")

    for seed in range(max_try):
        if len(selected) >= target:
            break

        result = evaluate_seed(seed, difficulty)
        all_results.append(result)

        ok = is_selected(result, difficulty)
        if ok:
            selected.append(seed)

        h_str = "pass" if result["healthy_pass"] else "FAIL"
        if result["disease_viable"] is None:
            d_str = "n/a"
        elif result["disease_viable"]:
            d_str = "ok"
        else:
            d_str = "FAIL"
        r_str = "SELECTED" if ok else "rejected"
        flags_str = ", ".join(result["flags"]) if result["flags"] else ""
        print(f"  {seed:>4}  {h_str:>8}  {d_str:>8}  {r_str:>8}  {flags_str}")

    print(f"\n  Selected {len(selected)}/{target} seeds: {selected}")
    if len(selected) < target:
        print(f"  WARNING: only {len(selected)} valid seeds found in {max_try} attempts")

    return {
        "difficulty": difficulty,
        "target": target,
        "selected_seeds": selected,
        "n_selected": len(selected),
        "n_tried": len(all_results),
        "details": all_results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=TARGET_SEEDS,
                        help=f"Number of valid seeds to select per tier (default: {TARGET_SEEDS})")
    parser.add_argument("--max-try", type=int, default=MAX_SEEDS_TO_TRY,
                        help=f"Max seeds to attempt (default: {MAX_SEEDS_TO_TRY})")
    parser.add_argument("--difficulty", default=None,
                        help="Run only this tier: easy, medium, hard (default: all)")
    args = parser.parse_args()

    difficulties = [args.difficulty] if args.difficulty else ["easy", "medium", "hard"]

    output: dict[str, list[int]] = {}
    all_tier_results = []

    for difficulty in difficulties:
        result = select_seeds(difficulty, args.target, args.max_try)
        output[difficulty] = result["selected_seeds"]
        all_tier_results.append(result)

    # Summary
    print(f"\n{'='*62}")
    print("  SELECTED SEEDS SUMMARY")
    print(f"{'='*62}")
    for tier, seeds in output.items():
        disease_note = " (also used for disease sweep)" if tier in DISEASE_TIERS else ""
        print(f"  {tier:>8}: {seeds}{disease_note}")

    # Save
    out_path = Path(__file__).parent / "selected_seeds.json"
    payload = {
        "target_per_tier": args.target,
        "seeds": output,
        "details": all_tier_results,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
