"""
Ambiguity vs diagnosis accuracy analysis — post-hoc, no API calls needed.

For each disease-mode session, extracts n_diagnosis_alternatives (number of
genes that could plausibly explain the observed phenotype deviation) and the
diagnosis score. Plots and reports the relationship across models and sweeps.

Usage
-----
    python experiments/paper_v1/analyse_ambiguity.py
    python experiments/paper_v1/analyse_ambiguity.py --sweep A_medium_disease
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def analyse_session(log_path: Path) -> dict | None:
    log = json.loads(log_path.read_text())
    summary = log.get("summary", {})
    meta = log.get("metadata", {})

    if not meta.get("disease_mode"):
        return None

    n_alts = summary.get("n_diagnosis_alternatives")
    if n_alts is None:
        return None

    hyp = summary.get("malfunction_hypothesis") or {}
    diagnosis_score = hyp.get("score")
    if diagnosis_score is None:
        return None

    # Determine sweep from directory structure
    sweep = log_path.parent.parent.name

    return {
        "model": meta.get("model", "unknown"),
        "seed": meta.get("seed"),
        "sweep": sweep,
        "difficulty": meta.get("difficulty", sweep.split("_")[1] if "_" in sweep else "unknown"),
        "n_diagnosis_alternatives": n_alts,
        "diagnosis_score": diagnosis_score,
        "rescue_fraction": summary.get("rescue_results", [{}])[0].get("restored_fraction")
            if summary.get("rescue_results") else None,
        "budget_used": summary.get("budget_used", 0),
    }


def _mean_std(values: list[float]) -> str:
    if not values:
        return "n/a"
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{m:.3f}±{s:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", default=None, help="Filter to a specific sweep")
    parser.add_argument("--model", default=None, help="Filter to a specific model")
    parser.add_argument("--plot", action="store_true", help="Generate scatter plot")
    args = parser.parse_args()

    logs_base = Path(__file__).parent / "logs"
    if not logs_base.exists():
        print(f"No logs found at {logs_base}")
        return

    records: list[dict] = []
    for sweep_dir in sorted(logs_base.iterdir()):
        if args.sweep and sweep_dir.name != args.sweep:
            continue
        # logs are nested one level: sweep_dir/logs/*.json
        log_dir = sweep_dir / "logs" if (sweep_dir / "logs").exists() else sweep_dir
        for log_file in sorted(log_dir.glob("*.json")):
            r = analyse_session(log_file)
            if r is None:
                continue
            if args.model and r["model"] != args.model:
                continue
            records.append(r)

    if not records:
        print("No disease-mode records found.")
        return

    print(f"\nAmbiguity vs diagnosis accuracy — Part 1 disease sessions\n")
    print(f"Total sessions: {len(records)}")
    print(f"n_diagnosis_alternatives range: "
          f"{min(r['n_diagnosis_alternatives'] for r in records)}–"
          f"{max(r['n_diagnosis_alternatives'] for r in records)}\n")

    # Group by ambiguity level
    by_ambiguity: dict[int, list[float]] = defaultdict(list)
    for r in records:
        by_ambiguity[r["n_diagnosis_alternatives"]].append(r["diagnosis_score"])

    print(f"{'Alternatives':>14}  {'Diag score':>12}  {'n':>4}")
    print(f"{'─'*36}")
    for n_alts in sorted(by_ambiguity):
        scores = by_ambiguity[n_alts]
        print(f"  {n_alts:>12}  {_mean_std(scores):>12}  {len(scores):>4}")

    # Per-model breakdown
    print(f"\nPer-model mean diagnosis score by ambiguity:\n")
    models = sorted({r["model"] for r in records})
    all_alts = sorted(by_ambiguity.keys())
    header = f"  {'Model':30s}" + "".join(f"  {'n='+str(a):>10}" for a in all_alts)
    print(header)
    for model in models:
        row = [f"  {model:30s}"]
        for a in all_alts:
            recs = [r for r in records if r["model"] == model
                    and r["n_diagnosis_alternatives"] == a]
            scores = [r["diagnosis_score"] for r in recs]
            row.append(f"  {_mean_std(scores):>10}")
        print("".join(row))

    # Save records
    out_path = Path(__file__).parent / "ambiguity_analysis.jsonl"
    with open(out_path, "w") as f:
        for r in sorted(records, key=lambda x: (x["model"], x["sweep"], x["seed"] or 0)):
            f.write(json.dumps(r) + "\n")
    print(f"\nPer-session records → {out_path}")

    if args.plot:
        _plot(records, models, all_alts)


def _plot(records, models, all_alts):
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left: mean diagnosis score vs ambiguity, all models
    ax = axes[0]
    colors = plt.cm.tab10.colors
    for i, model in enumerate(models):
        xs, ys, errs = [], [], []
        for a in all_alts:
            recs = [r for r in records if r["model"] == model
                    and r["n_diagnosis_alternatives"] == a]
            scores = [r["diagnosis_score"] for r in recs]
            if scores:
                xs.append(a)
                ys.append(statistics.mean(scores))
                errs.append(statistics.stdev(scores) if len(scores) > 1 else 0)
        if xs:
            ax.errorbar(xs, ys, yerr=errs, marker='o', label=model,
                       color=colors[i % len(colors)], capsize=3)
    ax.set_xlabel("n_diagnosis_alternatives")
    ax.set_ylabel("Diagnosis score")
    ax.set_title("Ambiguity vs diagnosis accuracy")
    ax.legend(fontsize=8)
    ax.set_ylim(-0.05, 1.05)
    ax.axhline(0.5, color='grey', lw=0.8, ls='--', label='partial credit')

    # Right: scatter of all sessions (diagnosis vs rescue)
    ax2 = axes[1]
    for i, model in enumerate(models):
        recs = [r for r in records if r["model"] == model
                and r["rescue_fraction"] is not None]
        xs = [r["diagnosis_score"] for r in recs]
        ys = [r["rescue_fraction"] for r in recs]
        # jitter for visibility
        xs_j = [x + np.random.uniform(-0.02, 0.02) for x in xs]
        ys_j = [y + np.random.uniform(-0.02, 0.02) for y in ys]
        ax2.scatter(xs_j, ys_j, label=model, alpha=0.6,
                   color=colors[i % len(colors)], s=30)
    ax2.set_xlabel("Diagnosis score")
    ax2.set_ylabel("Rescue fraction")
    ax2.set_title("Diagnosis vs rescue (all disease sessions)")
    ax2.legend(fontsize=8)
    ax2.set_xlim(-0.05, 1.05)
    ax2.set_ylim(-0.05, 1.05)

    plt.tight_layout()
    out = Path(__file__).parent / "ambiguity_analysis.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"Plot → {out}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    main()
