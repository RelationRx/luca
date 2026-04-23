"""
Backwards-ablation paired analysis.

Joins forward results from experiments/paper_v1/ with backwards results from
experiments/backwards_ablation/, computes per-model paired deltas, Wilcoxon
signed-rank tests, bootstrap 95% confidence intervals, and (if statsmodels is
installed) a mixed-effects interaction test.

Outputs
-------
experiments/backwards_ablation/backwards_stats.json — machine-readable results.
experiments/backwards_ablation/tables.md — paper-ready tables.

Usage
-----
python experiments/backwards_ablation/analyze.py
python experiments/backwards_ablation/analyze.py --mode healthy
python experiments/backwards_ablation/analyze.py --forward-dir experiments/paper_v1/results
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

ABLATION_DIR = Path(__file__).parent
DEFAULT_FORWARD_DIR = REPO_ROOT / "experiments" / "paper_v1" / "results"
DEFAULT_BACKWARD_DIR = ABLATION_DIR / "results"

# Paper's medium-tier sweep directory names.
FORWARD_SWEEP = {"healthy": "A_medium_healthy", "disease": "A_medium_disease"}

# Models in the ablation (see spec §2.2).
MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "deepseek-v3",
    "qwen-3.5",
    "gpt-5.1",
    "gpt-4o",
    "gpt-4.1",
    "heuristic",
]

BOOTSTRAP_ITERS = 1000


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_records(
    mode: str, forward_dir: Path, backward_dir: Path,
) -> dict[str, dict[str, list[dict]]]:
    """Return nested dict: model -> {'forward': [records], 'backward': [records]}."""
    out: dict[str, dict[str, list[dict]]] = {}
    fwd_sweep = FORWARD_SWEEP[mode]
    for model in MODELS:
        fwd_path = forward_dir / fwd_sweep / f"{model}.jsonl"
        bwd_path = backward_dir / mode / f"{model}.jsonl"
        out[model] = {
            "forward": _load_jsonl(fwd_path),
            "backward": _load_jsonl(bwd_path),
        }
    return out


def _pair_on_seed(records: dict[str, list[dict]]) -> list[tuple[int, float, float]]:
    """Return list of (seed, forward_score, backward_score) for seeds present in both."""
    fwd = {r["seed"]: r for r in records["forward"] if "error" not in r}
    bwd = {r["seed"]: r for r in records["backward"] if "error" not in r}
    common = sorted(set(fwd) & set(bwd))
    pairs: list[tuple[int, float, float]] = []
    for s in common:
        f = fwd[s].get("composite_score")
        b = bwd[s].get("composite_score")
        if f is None or b is None:
            continue
        pairs.append((s, float(f), float(b)))
    return pairs


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def _wilcoxon_signed_rank(diffs: list[float]) -> float | None:
    """Simple Wilcoxon signed-rank two-sided p-value. Returns None if too few
    non-zero diffs. For N ≥ 10, uses normal approximation."""
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n < 5:
        return None
    absd = sorted((abs(d), 1 if d > 0 else -1) for d in nonzero)
    # Average-rank handling of ties on |d|
    ranks: list[float] = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and absd[j + 1][0] == absd[i][0]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-indexed average rank
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1
    W_plus = sum(ranks[k] for k in range(n) if absd[k][1] > 0)
    W_minus = sum(ranks[k] for k in range(n) if absd[k][1] < 0)
    W = min(W_plus, W_minus)
    mu = n * (n + 1) / 4
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    if sigma == 0:
        return None
    z = (W - mu) / sigma
    # Two-sided p from normal approximation
    p = 2 * (1 - _phi(abs(z)))
    return round(p, 6)


def _phi(x: float) -> float:
    """Standard normal CDF via error function."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _bootstrap_ci(diffs: list[float], iters: int = BOOTSTRAP_ITERS, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile-bootstrap two-sided CI on the mean of `diffs`."""
    import random
    n = len(diffs)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = random.Random(42)
    means: list[float] = []
    for _ in range(iters):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(iters * alpha / 2)]
    hi = means[int(iters * (1 - alpha / 2))]
    return (round(lo, 4), round(hi, 4))


def _summary(pairs: list[tuple[int, float, float]]) -> dict[str, Any]:
    if not pairs:
        return {"n_pairs": 0}
    diffs = [f - b for _, f, b in pairs]
    forwards = [f for _, f, _ in pairs]
    backwards = [b for _, _, b in pairs]
    return {
        "n_pairs": len(pairs),
        "forward_mean": round(statistics.mean(forwards), 4),
        "forward_std": round(statistics.stdev(forwards), 4) if len(forwards) > 1 else 0.0,
        "backward_mean": round(statistics.mean(backwards), 4),
        "backward_std": round(statistics.stdev(backwards), 4) if len(backwards) > 1 else 0.0,
        "delta_mean": round(statistics.mean(diffs), 4),
        "delta_ci_95": _bootstrap_ci(diffs),
        "wilcoxon_p": _wilcoxon_signed_rank(diffs),
    }


def _mixed_effects_interaction(
    pairs_by_model: dict[str, list[tuple[int, float, float]]],
) -> dict[str, Any] | None:
    """Fit score ~ model * direction + (1|seed) if statsmodels is available.

    Returns None if statsmodels isn't installed — the rest of the analysis still
    runs.
    """
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except ImportError:
        return None

    rows: list[dict] = []
    for model, pairs in pairs_by_model.items():
        for seed, fwd, bwd in pairs:
            rows.append({"model": model, "seed": seed, "direction": "forward", "score": fwd})
            rows.append({"model": model, "seed": seed, "direction": "backward", "score": bwd})
    if not rows:
        return None
    df = pd.DataFrame(rows)

    model_fit = smf.mixedlm(
        "score ~ C(model) * C(direction)", df, groups=df["seed"],
    ).fit(method="lbfgs")

    interaction_terms = {
        name: {
            "coef": round(float(model_fit.params[name]), 4),
            "p": round(float(model_fit.pvalues[name]), 6),
        }
        for name in model_fit.params.index
        if ":C(direction)" in name
    }
    return {"n_rows": len(df), "interaction_terms": interaction_terms}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def analyze_mode(mode: str, forward_dir: Path, backward_dir: Path) -> dict[str, Any]:
    """Run the paired analysis for one mode ('healthy' or 'disease')."""
    loaded = load_records(mode, forward_dir, backward_dir)

    per_model: dict[str, Any] = {}
    pairs_by_model: dict[str, list] = {}
    for model, recs in loaded.items():
        pairs = _pair_on_seed(recs)
        pairs_by_model[model] = pairs
        per_model[model] = _summary(pairs)

    heur = per_model.get("heuristic", {})
    heuristic_gap = heur.get("delta_mean") if heur.get("n_pairs") else None
    if heuristic_gap is not None:
        for model, summary in per_model.items():
            if summary.get("n_pairs") and model != "heuristic":
                summary["delta_vs_heuristic"] = round(
                    summary["delta_mean"] - heuristic_gap, 4,
                )

    mixed = _mixed_effects_interaction(pairs_by_model)

    return {"per_model": per_model, "mixed_effects": mixed}


def format_tables_md(results: dict[str, dict[str, Any]]) -> str:
    """Render the per-model paired-delta tables."""
    lines = ["# Backwards-Ablation Results", ""]
    for mode in ("healthy", "disease"):
        mode_res = results.get(mode, {})
        per_model = mode_res.get("per_model", {})
        if not any(s.get("n_pairs") for s in per_model.values()):
            lines.append(f"## {mode.capitalize()} — no data yet")
            lines.append("")
            lines.append(
                "Run the sweep first: "
                "`python experiments/backwards_ablation/run.py --model …`"
            )
            lines.append("")
            continue
        lines.append(f"## {mode.capitalize()} (medium tier, paired per seed)")
        lines.append("")
        lines.append(
            "| Model | N | Forward | Backward | Δ (F−B) | 95% CI | Wilcoxon p | Δ − Δ_heuristic |"
        )
        lines.append("|---|---:|---:|---:|---:|:---:|---:|---:|")
        for model in MODELS:
            s = per_model.get(model, {})
            if not s.get("n_pairs"):
                continue
            ci_lo, ci_hi = s["delta_ci_95"]
            adj = s.get("delta_vs_heuristic")
            adj_str = f"{adj:+.3f}" if adj is not None else "—"
            p = s.get("wilcoxon_p")
            p_str = f"{p:.4f}" if p is not None else "—"
            lines.append(
                f"| {model} | {s['n_pairs']} | "
                f"{s['forward_mean']:.3f} ± {s['forward_std']:.3f} | "
                f"{s['backward_mean']:.3f} ± {s['backward_std']:.3f} | "
                f"**{s['delta_mean']:+.3f}** | "
                f"[{ci_lo:+.3f}, {ci_hi:+.3f}] | "
                f"{p_str} | {adj_str} |"
            )
        lines.append("")

        mixed = mode_res.get("mixed_effects")
        if mixed:
            lines.append(
                f"**Mixed-effects interaction** "
                f"(score ~ model × direction + (1|seed), N={mixed['n_rows']} rows):"
            )
            for term, stat in mixed["interaction_terms"].items():
                lines.append(f"- `{term}`: β = {stat['coef']:+.4f}, p = {stat['p']:.4f}")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", action="append", choices=["healthy", "disease"])
    parser.add_argument("--forward-dir", type=Path, default=DEFAULT_FORWARD_DIR)
    parser.add_argument("--backward-dir", type=Path, default=DEFAULT_BACKWARD_DIR)
    parser.add_argument(
        "--stats-out", type=Path,
        default=ABLATION_DIR / "backwards_stats.json",
    )
    parser.add_argument(
        "--tables-out", type=Path, default=ABLATION_DIR / "tables.md",
    )
    args = parser.parse_args()

    modes = args.mode or ["healthy", "disease"]
    results = {
        mode: analyze_mode(mode, args.forward_dir, args.backward_dir)
        for mode in modes
    }

    args.stats_out.write_text(json.dumps(results, indent=2) + "\n")
    args.tables_out.write_text(format_tables_md(results))
    print(f"Stats → {args.stats_out}")
    print(f"Tables → {args.tables_out}")


if __name__ == "__main__":
    main()
