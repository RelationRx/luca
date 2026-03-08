#!/usr/bin/env python3
"""Analyze LEMONOIDS scaling study results from results.jsonl.

Usage:
    python analyze.py          # plain-text pivot table + threshold summary
    python analyze.py --csv    # CSV output for spreadsheet import
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
RESULTS_PATH = STUDY_DIR / "results.jsonl"

BUDGET_MULTIPLIERS = [0.5, 1.0, 1.5]


def _gene_levels(records):
    return sorted({r["n_genes"] for r in records})


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        print(f"[analyze] No results found at {RESULTS_PATH}")
        return []
    records = []
    with open(RESULTS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


def mean_std(values: list) -> tuple[float | None, float | None]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    if len(vals) == 1:
        return vals[0], 0.0
    return statistics.mean(vals), statistics.stdev(vals)


def fmt_ms(mean: float | None, std: float | None, width: int = 14) -> str:
    if mean is None:
        return ("N/A").center(width)
    s = f"{mean:.3f}+-{std:.3f}"
    return s.ljust(width)


# ---------------------------------------------------------------------------
# Pivot table
# ---------------------------------------------------------------------------


def pivot_table(records: list[dict], csv_mode: bool = False) -> None:
    """Print (n_genes, budget_multiplier) → mean±std of key metrics."""

    if csv_mode:
        print(
            "n_genes,budget_multiplier,"
            "diag_score_mean,diag_score_std,"
            "rescue_frac_mean,rescue_frac_std,"
            "pred_acc_mean,pred_acc_std,"
            "budget_eff_mean,budget_eff_std,"
            "n_obs"
        )
    else:
        print("Pivot Table: mean +- std across seeds")
        print("─" * 95)
        print(
            f"{'n_genes':>8}  {'mult':>5}  "
            f"{'diag_score':>14}  {'rescue_frac':>14}  "
            f"{'pred_acc':>14}  {'budget_eff':>14}  "
            f"{'n_obs':>5}"
        )
        print("─" * 95)

    for n in _gene_levels(records):
        for m in BUDGET_MULTIPLIERS:
            subset = [
                r for r in records
                if r["n_genes"] == n and abs(r["budget_multiplier"] - m) < 1e-9
            ]

            diag_m, diag_s = mean_std([r["malfunction_score"] for r in subset])
            resc_m, resc_s = mean_std([r["best_rescue_fraction"] for r in subset])
            pred_m, pred_s = mean_std([r["avg_prediction_accuracy"] for r in subset])
            eff_vals = [
                r["budget_used"] / r["budget_total"]
                for r in subset
                if r.get("budget_total") and r["budget_total"] > 0
            ]
            eff_m, eff_s = mean_std(eff_vals)

            n_obs = len(subset)

            if csv_mode:
                def _fv(v):
                    return "" if v is None else f"{v:.6f}"
                print(
                    f"{n},{m:.2f},"
                    f"{_fv(diag_m)},{_fv(diag_s)},"
                    f"{_fv(resc_m)},{_fv(resc_s)},"
                    f"{_fv(pred_m)},{_fv(pred_s)},"
                    f"{_fv(eff_m)},{_fv(eff_s)},"
                    f"{n_obs}"
                )
            else:
                print(
                    f"{n:>8}  {m:>5.2f}  "
                    f"{fmt_ms(diag_m, diag_s):>14}  "
                    f"{fmt_ms(resc_m, resc_s):>14}  "
                    f"{fmt_ms(pred_m, pred_s):>14}  "
                    f"{fmt_ms(eff_m, eff_s):>14}  "
                    f"{n_obs:>5}"
                )

    if not csv_mode:
        print("─" * 95)


# ---------------------------------------------------------------------------
# Budget threshold summary
# ---------------------------------------------------------------------------


def budget_threshold_summary(records: list[dict], csv_mode: bool = False) -> None:
    """For each n_genes, the lowest multiplier where mean diag_score >= 0.8."""

    if csv_mode:
        print("n_genes,threshold_mult,mean_diag_score,n_obs")
    else:
        print()
        print("Budget Threshold: lowest multiplier with mean diag_score >= 0.8")
        print("─" * 60)
        print(f"{'n_genes':>8}  {'threshold_mult':>14}  {'mean_diag':>10}  {'n_obs':>5}")
        print("─" * 60)

    for n in _gene_levels(records):
        found_mult: float | None = None
        found_score: float | None = None
        found_obs: int = 0

        for m in sorted(BUDGET_MULTIPLIERS):
            subset = [
                r for r in records
                if r["n_genes"] == n and abs(r["budget_multiplier"] - m) < 1e-9
            ]
            diag_vals = [r["malfunction_score"] for r in subset if r["malfunction_score"] is not None]
            if not diag_vals:
                continue
            mean_score = statistics.mean(diag_vals)
            if mean_score >= 0.8:
                found_mult = m
                found_score = mean_score
                found_obs = len(subset)
                break

        if csv_mode:
            mult_str = f"{found_mult:.2f}" if found_mult is not None else ""
            score_str = f"{found_score:.6f}" if found_score is not None else ""
            print(f"{n},{mult_str},{score_str},{found_obs}")
        else:
            mult_str = f"{found_mult:.2f}x" if found_mult is not None else "none (<0.8 at all budgets)"
            score_str = f"{found_score:.3f}" if found_score is not None else ""
            print(
                f"{n:>8}  {mult_str:>14}  {score_str:>10}  {found_obs:>5}"
            )

    if not csv_mode:
        print("─" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze LEMONOIDS scaling study results")
    parser.add_argument(
        "--csv", action="store_true",
        help="Output comma-separated format for spreadsheet import",
    )
    args = parser.parse_args()

    records = load_results()
    if not records:
        return

    if not args.csv:
        print(f"[analyze] {len(records)} records from {RESULTS_PATH}")
        print()

    pivot_table(records, csv_mode=args.csv)

    if args.csv:
        print()

    budget_threshold_summary(records, csv_mode=args.csv)


if __name__ == "__main__":
    main()
