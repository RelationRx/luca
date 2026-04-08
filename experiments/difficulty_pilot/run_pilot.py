#!/usr/bin/env python3
"""Difficulty tier pilot: one disease organism per tier (easy / medium / hard).

Fixed: n_genes=20, seed=42, budget=1.0x recommended, model=claude-sonnet-4-6.

Usage:
    python run_pilot.py            # run all three tiers
    python run_pilot.py --dry-run  # print config without API calls
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from luca.generation import generate_disease_organism, DIFFICULTY_PRESETS
from luca.experiment import ExperimentSession, recommended_budget
from luca.agent import run_agent
from luca.report import export_session_html

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DIFFICULTIES = ["easy", "medium", "hard"]
N_GENES     = 20
SEED        = 0
N_MODULES   = 4
N_SIGNALS   = 3
N_PHENOTYPES = 3
MODEL       = "claude-sonnet-4-6"
MAX_TURNS   = 50

PILOT_DIR = Path(__file__).resolve().parent
LOGS_DIR  = PILOT_DIR / "logs"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def describe_tier(difficulty: str) -> str:
    p = DIFFICULTY_PRESETS[difficulty]
    return (
        f"steepness={p['sigmoid_steepness']}, "
        f"n_feedback={p['n_feedback']}, "
        f"latent={int(p['latent_fraction'] * 100)}%, "
        f"noise={p['noise_sigma']}"
    )


def run_one(difficulty: str, dry_run: bool) -> dict | None:
    org = generate_disease_organism(
        n_genes=N_GENES,
        n_modules=N_MODULES,
        n_signals=N_SIGNALS,
        n_phenotypes=N_PHENOTYPES,
        difficulty=difficulty,
        seed=SEED,
    )
    budget = recommended_budget(org)
    m0 = org.malfunctions[0]
    visible_genes = len(org.genes) - len(org.latent_genes)

    log_stem  = f"{difficulty}_n{N_GENES}_s{SEED}"
    log_path  = LOGS_DIR / f"{log_stem}.json"
    html_path = LOGS_DIR / f"{log_stem}.html"

    print(
        f"\n{'='*60}\n"
        f"  {difficulty.upper()}  —  {describe_tier(difficulty)}\n"
        f"  n_genes={N_GENES}, visible={visible_genes}, latent={len(org.latent_genes)}\n"
        f"  budget={budget}  malfunction={m0.type}/{m0.target_name}\n"
        f"{'='*60}"
    )

    if dry_run:
        print("  [dry-run] skipping API call")
        return None

    if log_path.exists():
        print(f"  [skip] log already exists: {log_path.name}")
        log_data = json.loads(log_path.read_text())
        summary = log_data.get("summary", {})
    else:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        session = ExperimentSession(org, budget=budget, seed=SEED)
        summary = run_agent(session, model=MODEL, max_turns=MAX_TURNS,
                            verbose=False, log_path=str(log_path))
        log_data = json.loads(log_path.read_text())
        export_session_html(log_data, str(html_path))

    mh   = summary.get("malfunction_hypothesis")
    rr   = summary.get("rescue_results", [])
    diag = mh["score"] if mh else None
    best_rescue = max((r["restored_fraction"] for r in rr), default=None)

    print(
        f"  diag_score={diag}  "
        f"best_rescue={best_rescue}  "
        f"pred_acc={summary.get('avg_accuracy')}  "
        f"budget_used={summary.get('budget_used')}/{budget}"
    )
    return {
        "difficulty": difficulty,
        "n_genes": N_GENES,
        "seed": SEED,
        "budget": budget,
        "visible_genes": visible_genes,
        "latent_genes": len(org.latent_genes),
        "malfunction_type": m0.type,
        "malfunction_target": m0.target_name,
        "malfunction_score": diag,
        "best_rescue_fraction": best_rescue,
        "avg_prediction_accuracy": summary.get("avg_accuracy"),
        "budget_used": summary.get("budget_used"),
    }


def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"  DIFFICULTY PILOT — SUMMARY")
    print(f"  n_genes={N_GENES}, seed={SEED}, model={MODEL}")
    print(f"{'='*60}")
    hdr = f"{'Tier':<8}  {'Visible':>7}  {'Latent':>6}  {'Diag':>6}  {'Rescue':>7}  {'Pred':>6}  {'Budget':>10}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        tier    = r["difficulty"]
        visible = r["visible_genes"]
        latent  = r["latent_genes"]
        diag    = f"{r['malfunction_score']:.1f}" if r["malfunction_score"] is not None else "  -"
        rescue  = f"{r['best_rescue_fraction']:.2f}" if r["best_rescue_fraction"] is not None else "   -"
        pred    = f"{r['avg_prediction_accuracy']:.2f}" if r["avg_prediction_accuracy"] is not None else "  -"
        used    = r["budget_used"] or "-"
        budget  = r["budget"]
        print(f"{tier:<8}  {visible:>7}  {latent:>6}  {diag:>6}  {rescue:>7}  {pred:>6}  {used:>4}/{budget}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results = []
    for diff in DIFFICULTIES:
        r = run_one(diff, dry_run=args.dry_run)
        if r is not None:
            results.append(r)

    if results and not args.dry_run:
        print_summary(results)
        out = PILOT_DIR / "results.json"
        out.write_text(json.dumps(results, indent=2))
        print(f"Results saved → {out}")


if __name__ == "__main__":
    main()
