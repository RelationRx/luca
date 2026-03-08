#!/usr/bin/env python3
"""2D sweep: n_genes × difficulty, single seed per cell.

For each cell the first valid seed in 0..MAX_SEED_SEARCH is used (one that
produces a disease organism with ≥1 aberrant phenotype and no warnings).

Usage:
    python run_2d.py            # run all 12 conditions
    python run_2d.py --dry-run  # print grid without API calls
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from lemonoids.generation import generate_disease_organism, DIFFICULTY_PRESETS
from lemonoids.experiment import ExperimentSession, recommended_budget
from lemonoids.agent import run_agent
from lemonoids.report import export_session_html
from lemonoids.dynamics import compute_phenotypes

# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

N_GENES_LEVELS = [10, 15, 20, 35]
DIFFICULTIES   = ["easy", "medium", "hard"]
BUDGET_MULT    = 1.0
MAX_SEED_SEARCH = 20

FIXED = dict(n_modules=4, n_signals=3, n_phenotypes=3)
MODEL    = "claude-sonnet-4-6"
MAX_TURNS = 50

STUDY_DIR = Path(__file__).resolve().parent
LOGS_DIR  = STUDY_DIR / "logs"
RESULTS_PATH = STUDY_DIR / "results.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_valid_organism(n_genes: int, difficulty: str):
    """Return (org, seed) for the first seed in 0..MAX_SEED_SEARCH that produces
    a disease organism with ≥1 aberrant phenotype and no generation warnings."""
    for seed in range(MAX_SEED_SEARCH):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            org = generate_disease_organism(
                n_genes=n_genes, difficulty=difficulty, seed=seed, **FIXED
            )
            had_warn = any(
                "No aberrant" in str(x.message) or "could not verify" in str(x.message)
                for x in w
            )
        phenos = compute_phenotypes(org, org.baseline_state, noise=False)
        aberrant = [
            l for l, v in phenos.items()
            if not (org.healthy_phenotype_ranges[l][0] <= v <= org.healthy_phenotype_ranges[l][1])
        ]
        if aberrant and not had_warn:
            return org, seed
    raise RuntimeError(
        f"No valid disease organism found for n_genes={n_genes}, difficulty={difficulty} "
        f"in seeds 0..{MAX_SEED_SEARCH - 1}"
    )


def log_stem(n: int, diff: str, seed: int) -> str:
    return f"n{n}_{diff}_s{seed}"


def extract_metrics(summary: dict, org, n: int, diff: str, seed: int, log_rel: str) -> dict:
    mh = summary.get("malfunction_hypothesis")
    rr = summary.get("rescue_results", [])
    m0 = org.malfunctions[0] if org.malfunctions else None
    return {
        "n_genes":              n,
        "difficulty":           diff,
        "seed":                 seed,
        "budget_total":         summary.get("budget_total"),
        "budget_used":          summary.get("budget_used"),
        "n_experiments":        summary.get("n_experiments", 0),
        "malfunction_type":     m0.type if m0 else None,
        "malfunction_target":   m0.target_name if m0 else None,
        "n_latent":             len(org.latent_genes),
        "malfunction_score":    mh["score"] if mh else None,
        "n_rescue_attempts":    len(rr),
        "best_rescue_fraction": max((r["restored_fraction"] for r in rr), default=None),
        "avg_prediction_accuracy": summary.get("avg_accuracy"),
        "avg_prediction_mse":   summary.get("avg_mse"),
        "log_path":             log_rel,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Pre-scan grid to find valid seeds
    print("Scouting valid seeds for all 12 conditions...")
    grid: list[tuple[int, str, "Organism", int]] = []
    for n in N_GENES_LEVELS:
        for diff in DIFFICULTIES:
            org, seed = find_valid_organism(n, diff)
            budget = max(5, round(recommended_budget(org) * BUDGET_MULT))
            m0 = org.malfunctions[0] if org.malfunctions else None
            log_rel  = f"logs/{log_stem(n, diff, seed)}.json"
            log_path = STUDY_DIR / log_rel
            exists   = log_path.exists()
            flag = "  [SKIP]" if exists else ""
            print(
                f"  n={n:>2}  {diff:<8}  seed={seed}  budget={budget:>3}  "
                f"{m0.type+'/'+m0.target_name if m0 else 'none':<18}  "
                f"latent={len(org.latent_genes)}{flag}"
            )
            grid.append((n, diff, org, seed))

    total = len(grid)
    n_new = sum(1 for n, d, o, s in grid if not (LOGS_DIR / f"{log_stem(n, d, s)}.json").exists())
    print(f"\n{total} conditions — {n_new} new runs\n")

    if args.dry_run:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    completed = skipped = 0

    for idx, (n, diff, org, seed) in enumerate(grid, 1):
        stem     = log_stem(n, diff, seed)
        log_path = LOGS_DIR / f"{stem}.json"
        html_path = LOGS_DIR / f"{stem}.html"
        log_rel  = f"logs/{stem}.json"

        if log_path.exists():
            # Back-fill results record if missing (e.g. previous crash after log write)
            already_recorded = any(
                r.get("n_genes") == n and r.get("difficulty") == diff and r.get("seed") == seed
                for r in (
                    [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]
                    if RESULTS_PATH.exists() else []
                )
            )
            if not already_recorded:
                log_data = json.loads(log_path.read_text())
                summary_bf = log_data.get("summary", {})
                record_bf = extract_metrics(summary_bf, org, n, diff, seed, log_rel)
                with open(RESULTS_PATH, "a") as f:
                    f.write(json.dumps(record_bf) + "\n")
                print(f"[{idx:>2}/{total}] BACKFILL  n={n}  {diff}  seed={seed}")
            else:
                skipped += 1
                print(f"[{idx:>2}/{total}] SKIP  n={n}  {diff}  seed={seed}")
            continue

        budget = max(5, round(recommended_budget(org) * BUDGET_MULT))
        m0 = org.malfunctions[0] if org.malfunctions else None

        print(
            f"[{idx:>2}/{total}] n={n:>2}  {diff:<8}  seed={seed}  "
            f"budget={budget}  malfunction={m0.type+'/'+m0.target_name if m0 else 'none'}"
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
