#!/usr/bin/env python3
"""Harder regimes sweep — two arms in one script.

Arm A — Large n: n=[75,100] × difficulty=[medium,hard] × seeds=[0,1,2] @ budget=1.0×
Arm B — Budget sensitivity: n=[35,50] × difficulty=hard × budget=[0.5×,0.75×] × seeds=[0,1,2]

Total: 24 new conditions (builds on medium_vs_hard results at 1.0×).

Usage:
    python run_sweep.py            # all 24 conditions (resume-safe)
    python run_sweep.py --dry-run
    python run_sweep.py --arm A    # large-n arm only
    python run_sweep.py --arm B    # budget-sensitivity arm only
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from luca.generation import generate_disease_organism
from luca.experiment import ExperimentSession, recommended_budget
from luca.agent import run_agent
from luca.report import export_session_html
from luca.dynamics import compute_phenotypes

# ---------------------------------------------------------------------------
# Grid definition
# ---------------------------------------------------------------------------

# Arm A: large n
ARM_A = [
    (n, diff, seed, 1.0)
    for n in [75, 100]
    for diff in ["medium", "hard"]
    for seed in [0, 1, 2]
]

# Arm B: budget sensitivity (hard only, new budget levels)
ARM_B = [
    (n, "hard", seed, mult)
    for n in [35, 50]
    for mult in [0.5, 0.75]
    for seed in [0, 1, 2]
]

FIXED     = dict(n_modules=4, n_signals=3, n_phenotypes=3)
MODEL     = "claude-sonnet-4-6"
MAX_TURNS = 60   # larger for n=100

STUDY_DIR    = Path(__file__).resolve().parent
LOGS_DIR     = STUDY_DIR / "logs"
RESULTS_PATH = STUDY_DIR / "results.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def log_stem(n: int, diff: str, seed: int, mult: float) -> str:
    return f"n{n}_{diff}_s{seed}_b{mult:.2f}x"


def extract_metrics(summary: dict, org, n: int, diff: str, seed: int,
                    mult: float, log_rel: str) -> dict:
    mh = summary.get("malfunction_hypothesis")
    rr = summary.get("rescue_results", [])
    m0 = org.malfunctions[0] if org.malfunctions else None
    return {
        "arm":                     "A" if mult == 1.0 else "B",
        "n_genes":                 n,
        "difficulty":              diff,
        "seed":                    seed,
        "budget_multiplier":       mult,
        "budget_total":            summary.get("budget_total"),
        "budget_used":             summary.get("budget_used"),
        "n_experiments":           summary.get("n_experiments", 0),
        "malfunction_type":        m0.type if m0 else None,
        "malfunction_target":      m0.target_name if m0 else None,
        "n_latent":                len(org.latent_genes),
        "malfunction_score":       mh["score"] if mh else None,
        "n_rescue_attempts":       len(rr),
        "best_rescue_fraction":    max((r["restored_fraction"] for r in rr), default=None),
        "avg_prediction_accuracy": summary.get("avg_accuracy"),
        "avg_prediction_mse":      summary.get("avg_mse"),
        "log_path":                log_rel,
    }


def already_recorded(n: int, diff: str, seed: int, mult: float) -> bool:
    if not RESULTS_PATH.exists():
        return False
    return any(
        r.get("n_genes") == n and r.get("difficulty") == diff
        and r.get("seed") == seed and r.get("budget_multiplier") == mult
        for r in (json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip())
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arm", choices=["A", "B"], default=None,
                        help="Run only arm A (large n) or B (budget sensitivity)")
    args = parser.parse_args()

    grid = []
    if args.arm in (None, "A"):
        grid += [("A", *c) for c in ARM_A]
    if args.arm in (None, "B"):
        grid += [("B", *c) for c in ARM_B]

    total = len(grid)

    # Pre-generate organisms
    print("Generating organisms...")
    orgs: dict = {}
    for arm, n, diff, seed, mult in grid:
        if (n, diff, seed) not in orgs:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                orgs[(n, diff, seed)] = generate_disease_organism(
                    n_genes=n, difficulty=diff, seed=seed, **FIXED
                )

    # Print grid
    n_new = sum(
        1 for _, n, diff, seed, mult in grid
        if not (LOGS_DIR / f"{log_stem(n, diff, seed, mult)}.json").exists()
    )
    print(f"\n{'Arm A — Large n':^45}  {'Arm B — Budget sensitivity':^45}")
    print(f"n=[75,100] × [medium,hard] × seeds=[0,1,2] @ 1.0×  |  "
          f"n=[35,50] × hard × [0.5×,0.75×] × seeds=[0,1,2]")
    print(f"\n{total} conditions — {n_new} new runs\n")

    print(f"  {'#':>3}  {'arm'}  {'n':>4}  {'diff':<8}  {'s'}  {'mult':>6}  "
          f"{'budget':>6}  {'latent':>6}  malfunction")
    print("  " + "─" * 70)

    for idx, (arm, n, diff, seed, mult) in enumerate(grid, 1):
        org    = orgs[(n, diff, seed)]
        rec    = recommended_budget(org)
        budget = max(5, round(rec * mult))
        m0     = org.malfunctions[0] if org.malfunctions else None
        exists = (LOGS_DIR / f"{log_stem(n, diff, seed, mult)}.json").exists()
        flag   = "  [skip]" if exists else ""
        print(
            f"  {idx:>3}  {arm}    {n:>4}  {diff:<8}  {seed}  {mult:.2f}x  "
            f"{budget:>6}  {len(org.latent_genes):>6}  "
            f"{m0.type+'/'+m0.target_name if m0 else 'none'}{flag}"
        )

    if args.dry_run:
        return

    print()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    completed = skipped = 0

    for idx, (arm, n, diff, seed, mult) in enumerate(grid, 1):
        org      = orgs[(n, diff, seed)]
        stem     = log_stem(n, diff, seed, mult)
        log_path = LOGS_DIR / f"{stem}.json"
        html_path = LOGS_DIR / f"{stem}.html"
        log_rel  = f"logs/{stem}.json"
        rec      = recommended_budget(org)
        budget   = max(5, round(rec * mult))
        m0       = org.malfunctions[0] if org.malfunctions else None

        if log_path.exists():
            if not already_recorded(n, diff, seed, mult):
                log_data   = json.loads(log_path.read_text())
                summary_bf = log_data.get("summary", {})
                record_bf  = extract_metrics(summary_bf, org, n, diff, seed, mult, log_rel)
                with open(RESULTS_PATH, "a") as f:
                    f.write(json.dumps(record_bf) + "\n")
                print(f"[{idx:>2}/{total}] BACKFILL  n={n}  {diff}  s={seed}  {mult:.2f}x")
            else:
                skipped += 1
                print(f"[{idx:>2}/{total}] SKIP      n={n}  {diff}  s={seed}  {mult:.2f}x")
            continue

        print(
            f"[{idx:>2}/{total}] arm={arm}  n={n:>3}  {diff:<8}  s={seed}  "
            f"{mult:.2f}x  budget={budget}  latent={len(org.latent_genes)}  "
            f"{m0.type+'/'+m0.target_name if m0 else 'none'}"
        )

        session = ExperimentSession(org, budget=budget, seed=seed)
        summary = run_agent(session, model=MODEL, max_turns=MAX_TURNS,
                            verbose=False, log_path=str(log_path))

        record = extract_metrics(summary, org, n, diff, seed, mult, log_rel)
        print(
            f"       → diag={record['malfunction_score']}  "
            f"rescue={record['best_rescue_fraction']}  "
            f"pred={record['avg_prediction_accuracy']}  "
            f"used={record['budget_used']}/{budget}"
        )

        with open(RESULTS_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
        completed += 1

        try:
            log_data = json.loads(log_path.read_text())
            export_session_html(log_data, str(html_path))
        except Exception as e:
            print(f"       [warn] HTML export failed: {e}")

    print(f"\nDone. Completed={completed}  Skipped={skipped}")
    print(f"Results → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
