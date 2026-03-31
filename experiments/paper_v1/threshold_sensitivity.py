"""
Threshold sensitivity analysis.

Recomputes prediction accuracy at multiple ±threshold values using the
per-phenotype ground_truth/prediction pairs stored in session logs.
Checks whether the Claude > GPT performance gap holds at tighter thresholds.

Usage:
    python experiments/paper_v1/threshold_sensitivity.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"

SWEEPS = {
    "B_easy_healthy":   {"difficulty": "easy",   "disease": False},
    "A_medium_healthy": {"difficulty": "medium",  "disease": False},
    "B_hard_healthy":   {"difficulty": "hard",    "disease": False},
    "A_medium_disease": {"difficulty": "medium",  "disease": True},
}

LLM_MODELS = ["claude-opus-4-6", "claude-sonnet-4-6", "gpt-5.1", "gpt-4o", "gpt-4.1"]

# Thresholds to evaluate. 0.10 is the canonical value.
THRESHOLDS = [0.15, 0.10, 0.08, 0.07, 0.05]

CANONICAL_SEEDS = set(range(20))

# Disease mode: gpt-5.1 excluded (too few valid seeds); gpt-4.1 kept with caveat.
DISEASE_EXCLUDE = {"gpt-5.1"}


def phenotype_accuracy(phenotypes: dict, threshold: float) -> float:
    """Fraction of phenotypes within ±threshold of ground truth."""
    results = [
        abs(v["prediction"] - v["ground_truth"]) <= threshold
        for v in phenotypes.values()
        if "prediction" in v and "ground_truth" in v
    ]
    return sum(results) / len(results) if results else float("nan")


def load_per_phenotype_accuracy(threshold: float) -> dict[str, dict[str, list[float]]]:
    """
    Returns {sweep: {model: [per-seed accuracy, ...]}} computed at the given threshold.
    Only canonical seeds 0-19 are included.
    """
    data: dict[str, dict[str, list[float]]] = {s: {} for s in SWEEPS}

    for sweep in SWEEPS:
        sweep_logs = LOGS_DIR / sweep / "logs"
        if not sweep_logs.exists():
            continue
        for path in sorted(sweep_logs.glob("*.json")):
            try:
                log = json.loads(path.read_text())
            except Exception:
                continue
            m = log.get("metadata", {})
            s = log.get("summary", {})
            seed = m.get("seed")
            if seed not in CANONICAL_SEEDS:
                continue
            model = m.get("model", path.stem.rsplit("_seed", 1)[0])

            pred_results = s.get("prediction_results") or []
            if not pred_results:
                continue

            # Average accuracy across prediction tasks at this threshold
            task_accs = []
            for task in pred_results:
                phenotypes = task.get("phenotypes") or {}
                if phenotypes:
                    task_accs.append(phenotype_accuracy(phenotypes, threshold))
            if not task_accs:
                continue

            avg_acc = statistics.mean(task_accs)
            data[sweep].setdefault(model, []).append(avg_acc)

    return data


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return m, s


def print_table(sweep: str, label: str, disease: bool = False) -> None:
    print(f"\n{'=' * 72}")
    print(f"{label}  —  thresholds: {', '.join(f'±{t}' for t in THRESHOLDS)}")
    print(f"{'=' * 72}")

    col_w = 13
    header = f"  {'Model':<22}" + "".join(f"  {'±'+str(t):>{col_w}}" for t in THRESHOLDS)
    print(header)
    print("  " + "-" * (len(header) - 2))

    # Load data at each threshold
    all_data = {t: load_per_phenotype_accuracy(t) for t in THRESHOLDS}

    models = [m for m in LLM_MODELS if not (disease and m in DISEASE_EXCLUDE)]
    for model in models:
        row = f"  {model:<22}"
        for t in THRESHOLDS:
            values = all_data[t].get(sweep, {}).get(model, [])
            m_val, s_val = mean_std(values)
            n = len(values)
            if n == 0:
                row += f"  {'—':>{col_w}}"
            else:
                cell = f"{m_val:.3f}±{s_val:.3f}"
                suffix = "" if n >= 18 else f"(n={n})"
                row += f"  {cell+suffix:>{col_w}}"
        print(row)

    # Claude vs best-GPT gap at each threshold
    print(f"\n  Claude–GPT gap (Opus vs best-GPT mean, per threshold):")
    gap_row = f"  {'':22}"
    for t in THRESHOLDS:
        sweep_data = all_data[t].get(sweep, {})
        opus   = mean_std(sweep_data.get("claude-opus-4-6", []))[0]
        gpt_scores = [
            mean_std(sweep_data.get(m, []))[0]
            for m in ["gpt-5.1", "gpt-4o", "gpt-4.1"]
            if sweep_data.get(m) and not (disease and m in DISEASE_EXCLUDE)
        ]
        best_gpt = max(gpt_scores) if gpt_scores else float("nan")
        gap = opus - best_gpt
        gap_row += f"  {gap:>+{col_w}.3f}"
    print(gap_row)


def main() -> None:
    print_table("B_easy_healthy",   "EASY   HEALTHY")
    print_table("A_medium_healthy", "MEDIUM HEALTHY")
    print_table("B_hard_healthy",   "HARD   HEALTHY")
    print_table("A_medium_disease", "MEDIUM DISEASE  (gpt-5.1 excluded)", disease=True)

    # Summary: does gap hold across thresholds?
    print(f"\n{'=' * 72}")
    print("SUMMARY — Claude-Opus vs best-GPT gap across thresholds")
    print(f"{'=' * 72}")
    print(f"  (positive = Claude leads; gap should hold or widen as threshold tightens)")
    print()

    col_w = 10
    header = f"  {'Sweep':<22}" + "".join(f"  {'±'+str(t):>{col_w}}" for t in THRESHOLDS)
    print(header)
    print("  " + "-" * (len(header) - 2))

    sweep_labels = {
        "B_easy_healthy":   "Easy healthy",
        "A_medium_healthy": "Medium healthy",
        "B_hard_healthy":   "Hard healthy",
        "A_medium_disease": "Medium disease",
    }
    for sweep, label in sweep_labels.items():
        disease = sweep.endswith("disease")
        row = f"  {label:<22}"
        for t in THRESHOLDS:
            data = load_per_phenotype_accuracy(t).get(sweep, {})
            opus = mean_std(data.get("claude-opus-4-6", []))[0]
            gpt_scores = [
                mean_std(data.get(m, []))[0]
                for m in ["gpt-5.1", "gpt-4o", "gpt-4.1"]
                if data.get(m) and not (disease and m in DISEASE_EXCLUDE)
            ]
            best_gpt = max(gpt_scores) if gpt_scores else float("nan")
            gap = opus - best_gpt
            row += f"  {gap:>+{col_w}.3f}"
        print(row)


if __name__ == "__main__":
    main()
