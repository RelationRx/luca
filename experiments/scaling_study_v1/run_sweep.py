#!/usr/bin/env python3
"""Scaling study sweep: malfunction diagnosis vs n_genes × budget × seed.

Usage:
    python run_sweep.py             # full 27-condition sweep (resume-safe)
    python run_sweep.py --dry-run   # print grid without API calls
    python run_sweep.py --filter-genes 10   # run only n_genes=10 slice
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make luca importable from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from luca.generation import generate_disease_organism
from luca.experiment import ExperimentSession, recommended_budget
from luca.agent import run_agent
from luca.report import export_session_html

# ---------------------------------------------------------------------------
# Grid definition
# ---------------------------------------------------------------------------

N_GENES_LEVELS = [10, 15, 20, 35]
BUDGET_MULTIPLIERS = [0.5, 1.0, 1.5]
SEEDS = [0, 1, 2]

FIXED = dict(
    n_modules=4,
    n_signals=3,
    n_phenotypes=3,
    n_malfunctions=1,
)

MODEL = "claude-sonnet-4-6"
MAX_TURNS = 50

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

STUDY_DIR = Path(__file__).resolve().parent
LOGS_DIR = STUDY_DIR / "logs"
METADATA_PATH = STUDY_DIR / "metadata.json"
RESULTS_PATH = STUDY_DIR / "results.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def log_filename(n_genes: int, seed: int, multiplier: float) -> str:
    return f"n{n_genes}_s{seed}_b{multiplier:.2f}x.json"


def html_filename(n_genes: int, seed: int, multiplier: float) -> str:
    return f"n{n_genes}_s{seed}_b{multiplier:.2f}x.html"


def build_grid() -> list[tuple[int, int, int, float]]:
    """Return list of (index, n_genes, seed, multiplier) tuples."""
    conditions = []
    idx = 1
    for n in N_GENES_LEVELS:
        for s in SEEDS:
            for m in BUDGET_MULTIPLIERS:
                conditions.append((idx, n, s, m))
                idx += 1
    return conditions


def ensure_metadata() -> None:
    """Write metadata.json once if it doesn't exist."""
    if METADATA_PATH.exists():
        return
    meta = {
        "study": "scaling_study_v1",
        "description": (
            "Factorial sweep: n_genes × budget_multiplier × seed. "
            "Disease mode only. Measures how malfunction diagnosis score "
            "and rescue quality scale with organism complexity and experiment budget."
        ),
        "date_created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "n_genes_levels": N_GENES_LEVELS,
        "budget_multipliers": BUDGET_MULTIPLIERS,
        "seeds": SEEDS,
        "fixed": {**FIXED, "max_turns": MAX_TURNS, "disease_mode": True},
    }
    METADATA_PATH.write_text(json.dumps(meta, indent=2))
    print(f"[sweep] Metadata written → {METADATA_PATH}")


def extract_metrics(
    summary: dict,
    n_genes: int,
    seed: int,
    multiplier: float,
    org,
    log_path_rel: str,
) -> dict:
    """Extract the metrics record to append to results.jsonl."""
    mh = summary.get("malfunction_hypothesis")
    rescue_results = summary.get("rescue_results", [])

    malfunction_score = mh["score"] if mh else None
    best_rescue_fraction = (
        max(r["restored_fraction"] for r in rescue_results)
        if rescue_results else None
    )
    best_rescue_mse = (
        min(r["mse_vs_healthy"] for r in rescue_results)
        if rescue_results else None
    )

    # Ground-truth malfunction info from organism
    m0 = org.malfunctions[0] if org.malfunctions else None

    return {
        "n_genes": n_genes,
        "seed": seed,
        "budget_multiplier": multiplier,
        "budget_total": summary["budget_total"],
        "budget_used": summary["budget_used"],
        "n_experiments": summary.get("n_experiments", 0),
        "malfunction_type": m0.type if m0 else None,
        "malfunction_target": m0.target_name if m0 else None,
        "malfunction_score": malfunction_score,
        "n_rescue_attempts": len(rescue_results),
        "best_rescue_fraction": best_rescue_fraction,
        "best_rescue_mse": best_rescue_mse,
        "avg_prediction_accuracy": summary.get("avg_accuracy"),
        "avg_prediction_mse": summary.get("avg_mse"),
        "log_path": log_path_rel,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="LUCA scaling study sweep")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the full grid without making API calls",
    )
    parser.add_argument(
        "--filter-genes", type=int, default=None, metavar="N",
        help="Run only the n_genes=N slice",
    )
    parser.add_argument(
        "--seed", type=int, default=None, metavar="S",
        help="Run only a single seed (drops replicates)",
    )
    args = parser.parse_args()

    grid = build_grid()
    total = len(grid)

    if args.filter_genes is not None:
        grid = [(i, n, s, m) for i, n, s, m in grid if n == args.filter_genes]
        if not grid:
            print(f"[sweep] No conditions match --filter-genes {args.filter_genes}")
            return

    if args.seed is not None:
        grid = [(i, n, s, m) for i, n, s, m in grid if s == args.seed]
        if not grid:
            print(f"[sweep] No conditions match --seed {args.seed}")
            return

    print(f"[sweep] Scaling study v1  —  {len(grid)}/{total} conditions")
    print(f"[sweep] Model: {MODEL}  Max turns: {MAX_TURNS}")
    print()

    if args.dry_run:
        # Show grid using the analytic budget formula (no API calls, no organism generation)
        print("DRY RUN — conditions and budgets:")
        print(
            f"{'#':>4}  {'n_genes':>7}  {'seed':>4}  {'mult':>5}  "
            f"{'rec':>5}  {'budget':>6}  log_path"
        )
        print("─" * 80)
        for i, n, s, m in grid:
            rec = n + FIXED["n_signals"] + 8          # n_genes + 3 signals + 8 overhead
            budget = max(5, round(rec * m))
            lp = log_filename(n, s, m)
            exists = (LOGS_DIR / lp).exists()
            flag = "  [SKIP - exists]" if exists else ""
            print(
                f"{i:>4}  {n:>7}  {s:>4}  {m:>5.2f}  "
                f"{rec:>5}  {budget:>6}  logs/{lp}{flag}"
            )
        return

    # Setup
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_metadata()

    completed = 0
    skipped = 0

    for i, n, s, m in grid:
        log_fname = log_filename(n, s, m)
        html_fname = html_filename(n, s, m)
        log_path = LOGS_DIR / log_fname
        html_path = LOGS_DIR / html_fname
        log_path_rel = f"logs/{log_fname}"

        # Resume-safe: skip completed runs
        if log_path.exists():
            skipped += 1
            print(
                f"[{i}/{total}] SKIP  n_genes={n}  seed={s}  "
                f"mult={m:.2f}x  (log exists)"
            )
            continue

        # Generate disease organism
        org = generate_disease_organism(
            n_genes=n,
            seed=s,
            **FIXED,
        )

        rec_budget = recommended_budget(org)
        budget = max(5, round(rec_budget * m))

        # Ground-truth malfunction label for console
        m0 = org.malfunctions[0] if org.malfunctions else None
        malfunction_str = f"{m0.type}/{m0.target_name}" if m0 else "none"

        print(
            f"[{i}/{total}] n_genes={n}  seed={s}  "
            f"budget={budget} ({m:.2f}x rec={rec_budget})  malfunction={malfunction_str}"
        )

        session = ExperimentSession(org, budget=budget, seed=s)

        summary = run_agent(
            session,
            model=MODEL,
            max_turns=MAX_TURNS,
            verbose=False,
            log_path=str(log_path),
        )

        # Generate HTML report from saved log
        with open(log_path) as f:
            log_data = json.load(f)
        export_session_html(log_data, str(html_path))

        # Extract metrics
        record = extract_metrics(summary, n, s, m, org, log_path_rel)

        diag = record["malfunction_score"]
        rescue = record["best_rescue_fraction"]
        pred = record["avg_prediction_accuracy"]
        bu = record["budget_used"]
        bt = record["budget_total"]

        diag_str = f"{diag:.2f}" if diag is not None else "N/A"
        rescue_str = f"{rescue:.2f}" if rescue is not None else "N/A"
        pred_str = f"{pred:.2f}" if pred is not None else "N/A"

        print(
            f"       → diag_score={diag_str}  rescue={rescue_str}  "
            f"pred_acc={pred_str}  budget_used={bu}/{bt}"
        )

        # Append to results.jsonl
        with open(RESULTS_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")

        completed += 1

    print()
    print(f"[sweep] Done.  Completed={completed}  Skipped={skipped}")


if __name__ == "__main__":
    main()
