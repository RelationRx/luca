#!/usr/bin/env python3
"""Medium vs Hard sweep: n_genes × difficulty × seed.

Grid: n_genes=[20,35,50] × difficulty=[medium,hard] × seeds=[0,1,2]
      budget=1.0× recommended, model=claude-sonnet-4-6

Usage:
    python run_sweep.py            # full 18-condition sweep (resume-safe)
    python run_sweep.py --dry-run  # print grid without API calls
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from lemonoids.generation import generate_disease_organism
from lemonoids.experiment import ExperimentSession, recommended_budget
from lemonoids.agent import run_agent
from lemonoids.report import export_session_html
from lemonoids.dynamics import compute_phenotypes

# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

N_GENES_LEVELS = [20, 35, 50]
DIFFICULTIES   = ["medium", "hard"]
SEEDS          = [0, 1, 2]
BUDGET_MULT    = 1.0

FIXED     = dict(n_modules=4, n_signals=3, n_phenotypes=3)
MODEL     = "claude-sonnet-4-6"
MAX_TURNS = 50

STUDY_DIR    = Path(__file__).resolve().parent
LOGS_DIR     = STUDY_DIR / "logs"
RESULTS_PATH = STUDY_DIR / "results.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def log_stem(n: int, diff: str, seed: int) -> str:
    return f"n{n}_{diff}_s{seed}"


def extract_metrics(summary: dict, org, n: int, diff: str, seed: int, log_rel: str) -> dict:
    mh = summary.get("malfunction_hypothesis")
    rr = summary.get("rescue_results", [])
    m0 = org.malfunctions[0] if org.malfunctions else None
    return {
        "n_genes":                 n,
        "difficulty":              diff,
        "seed":                    seed,
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


def already_recorded(n: int, diff: str, seed: int) -> bool:
    if not RESULTS_PATH.exists():
        return False
    return any(
        r.get("n_genes") == n and r.get("difficulty") == diff and r.get("seed") == seed
        for r in (json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip())
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Build full grid
    grid = [
        (n, diff, seed)
        for n in N_GENES_LEVELS
        for diff in DIFFICULTIES
        for seed in SEEDS
    ]
    total = len(grid)

    # Pre-generate organisms (fast — no API calls)
    orgs: dict[tuple, object] = {}
    for n, diff, seed in grid:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            orgs[(n, diff, seed)] = generate_disease_organism(
                n_genes=n, difficulty=diff, seed=seed, **FIXED
            )

    # Print grid
    n_new = sum(
        1 for n, diff, seed in grid
        if not (LOGS_DIR / f"{log_stem(n, diff, seed)}.json").exists()
    )
    print(f"Grid: {total} conditions — {n_new} new runs\n")
    print(f"  {'#':>3}  {'n':>4}  {'diff':<8}  {'seed'}  {'budget':>6}  {'latent':>6}  {'malfunction'}")
    print("  " + "-" * 62)
    for idx, (n, diff, seed) in enumerate(grid, 1):
        org    = orgs[(n, diff, seed)]
        budget = max(5, round(recommended_budget(org) * BUDGET_MULT))
        m0     = org.malfunctions[0] if org.malfunctions else None
        exists = (LOGS_DIR / f"{log_stem(n, diff, seed)}.json").exists()
        flag   = "  [skip]" if exists else ""
        print(
            f"  {idx:>3}  {n:>4}  {diff:<8}  {seed}  {budget:>6}  "
            f"{len(org.latent_genes):>6}  "
            f"{m0.type+'/'+m0.target_name if m0 else 'none'}{flag}"
        )

    if args.dry_run:
        return

    print()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    completed = skipped = 0

    for idx, (n, diff, seed) in enumerate(grid, 1):
        org      = orgs[(n, diff, seed)]
        stem     = log_stem(n, diff, seed)
        log_path = LOGS_DIR / f"{stem}.json"
        html_path = LOGS_DIR / f"{stem}.html"
        log_rel  = f"logs/{stem}.json"
        budget   = max(5, round(recommended_budget(org) * BUDGET_MULT))
        m0       = org.malfunctions[0] if org.malfunctions else None

        # Back-fill results record if log exists but record missing
        if log_path.exists():
            if not already_recorded(n, diff, seed):
                log_data   = json.loads(log_path.read_text())
                summary_bf = log_data.get("summary", {})
                record_bf  = extract_metrics(summary_bf, org, n, diff, seed, log_rel)
                with open(RESULTS_PATH, "a") as f:
                    f.write(json.dumps(record_bf) + "\n")
                print(f"[{idx:>2}/{total}] BACKFILL  n={n}  {diff}  seed={seed}")
            else:
                skipped += 1
                print(f"[{idx:>2}/{total}] SKIP      n={n}  {diff}  seed={seed}")
            continue

        print(
            f"[{idx:>2}/{total}] n={n:>2}  {diff:<8}  seed={seed}  "
            f"budget={budget}  latent={len(org.latent_genes)}  "
            f"malfunction={m0.type+'/'+m0.target_name if m0 else 'none'}"
        )

        session = ExperimentSession(org, budget=budget, seed=seed)
        summary = run_agent(session, model=MODEL, max_turns=MAX_TURNS,
                            verbose=False, log_path=str(log_path))

        record = extract_metrics(summary, org, n, diff, seed, log_rel)
        diag   = record["malfunction_score"]
        rescue = record["best_rescue_fraction"]
        pred   = record["avg_prediction_accuracy"]
        print(
            f"       → diag={diag}  rescue={rescue}  "
            f"pred={pred}  used={record['budget_used']}/{budget}"
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
