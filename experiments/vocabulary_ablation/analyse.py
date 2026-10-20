"""
Vocabulary + prompt-permission ablation analysis.

Reproduces the headline ablation tables:
  1. Per-cell accuracy means and standard deviations (2x2x2 design).
  2. Paired Wilcoxon signed-rank tests, permit - suppress (same vocab,
     same seed).
  3. Paired Wilcoxon signed-rank tests, real - invented (same prompt
     variant, same seed).

Usage:
    python experiments/vocabulary_ablation/analyse.py
    python experiments/vocabulary_ablation/analyse.py --csv table.csv

Requires scipy. Reads result JSONLs from experiments/vocabulary_ablation/results/
(local only — regenerate by running experiments/vocabulary_ablation/run.py).
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from scipy.stats import wilcoxon


RESULTS = Path(__file__).parent / "results"

MODELS = ["claude-opus-4-6", "deepseek-v3"]
DIFFICULTIES = ["medium", "hard"]
VOCABULARIES = ["invented", "real"]
VARIANTS = ["suppress", "permit"]


def sweep_dir(difficulty: str, vocab: str, variant: str) -> Path:
    """Directory convention: 'suppress' is implicit (no suffix)."""
    base = f"{difficulty}_{vocab}"
    name = base if variant == "suppress" else f"{base}_{variant}"
    return RESULTS / name


def load_cell(difficulty: str, vocab: str, variant: str, model: str) -> dict[int, dict]:
    """Return {seed: record} for one (difficulty, vocab, variant, model) cell."""
    path = sweep_dir(difficulty, vocab, variant) / f"{model}.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing results file: {path}\n"
            f"Run experiments/vocabulary_ablation/run.py to regenerate."
        )
    return {
        rec["seed"]: rec
        for rec in (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    }


def scores(cell: dict[int, dict]) -> list[float]:
    return [r["avg_accuracy"] for r in cell.values() if r.get("avg_accuracy") is not None]


def paired(a: dict[int, dict], b: dict[int, dict]) -> list[tuple[float, float]]:
    """Seeds present in both, with non-None avg_accuracy on both sides."""
    out = []
    for seed in a:
        if seed in b:
            x = a[seed].get("avg_accuracy")
            y = b[seed].get("avg_accuracy")
            if x is not None and y is not None:
                out.append((x, y))
    return out


def wilcoxon_p(pairs: list[tuple[float, float]]) -> float:
    """Paired Wilcoxon on non-zero diffs. Returns 1.0 if all diffs zero."""
    diffs = [b - a for a, b in pairs if a != b]
    if not diffs:
        return 1.0
    return float(wilcoxon(diffs).pvalue)


def per_cell_table() -> list[dict]:
    rows = []
    for m in MODELS:
        for d in DIFFICULTIES:
            for v in VOCABULARIES:
                for pv in VARIANTS:
                    s = scores(load_cell(d, v, pv, m))
                    rows.append({
                        "model": m,
                        "difficulty": d,
                        "vocabulary": v,
                        "variant": pv,
                        "n": len(s),
                        "mean": statistics.mean(s),
                        "sd": statistics.stdev(s) if len(s) > 1 else 0.0,
                        "median": statistics.median(s),
                    })
    return rows


def print_per_cell(rows: list[dict]) -> None:
    print("=" * 78)
    print("Per-cell accuracy (avg_accuracy, n=20 per cell)")
    print("=" * 78)
    print(f"{'model':<20} {'diff':<7} {'vocab':<9} {'variant':<9} {'n':>3} {'mean':>6} {'±sd':>6} {'median':>7}")
    for r in rows:
        print(f"{r['model']:<20} {r['difficulty']:<7} {r['vocabulary']:<9} {r['variant']:<9} "
              f"{r['n']:>3} {r['mean']:>6.3f} {r['sd']:>6.3f} {r['median']:>7.3f}")


def print_permit_vs_suppress() -> None:
    print()
    print("=" * 78)
    print("Paired Wilcoxon: permit - suppress  (same vocab, same seed)")
    print("=" * 78)
    print(f"{'model':<20} {'diff':<7} {'vocab':<9} {'n':>3} {'meanΔ':>8} {'p':>7}")
    for m in MODELS:
        for d in DIFFICULTIES:
            for v in VOCABULARIES:
                sup = load_cell(d, v, "suppress", m)
                per = load_cell(d, v, "permit", m)
                pairs = paired(sup, per)
                if not pairs:
                    continue
                mean_d = statistics.mean(b - a for a, b in pairs)
                p = wilcoxon_p(pairs)
                print(f"{m:<20} {d:<7} {v:<9} {len(pairs):>3} {mean_d:>+8.3f} {p:>7.3f}")


def print_real_vs_invented() -> None:
    print()
    print("=" * 78)
    print("Paired Wilcoxon: real - invented  (same variant, same seed)")
    print("=" * 78)
    print(f"{'model':<20} {'diff':<7} {'variant':<9} {'n':>3} {'meanΔ':>8} {'p':>7}")
    for m in MODELS:
        for d in DIFFICULTIES:
            for pv in VARIANTS:
                inv = load_cell(d, "invented", pv, m)
                rea = load_cell(d, "real", pv, m)
                pairs = paired(inv, rea)
                if not pairs:
                    continue
                mean_d = statistics.mean(b - a for a, b in pairs)
                p = wilcoxon_p(pairs)
                print(f"{m:<20} {d:<7} {pv:<9} {len(pairs):>3} {mean_d:>+8.3f} {p:>7.3f}")


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote per-cell table -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--csv", type=Path, default=None,
                        help="Optional: write per-cell table to this CSV path.")
    args = parser.parse_args()

    rows = per_cell_table()
    print_per_cell(rows)
    print_permit_vs_suppress()
    print_real_vs_invented()

    if args.csv:
        write_csv(rows, args.csv)


if __name__ == "__main__":
    main()
