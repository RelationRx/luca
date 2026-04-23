"""
Backwards-ablation figures.

Reads per-model JSONL (forward from experiments/paper_v1/, backward from
experiments/backwards_ablation/) and writes:

- panel_a_delta.png — paired-delta bar chart per model (Panel A)
- panel_b_scatter.png — forward vs backward scatter with identity line (Panel B)
- disease_subscores.png — 3-panel pred_acc / diagnosis / rescue deltas (disease mode)

All figures gracefully skip models with no paired data and emit a placeholder
title if NO data is available — useful for dry-runs before the sweep is run.

Usage
-----
python experiments/backwards_ablation/plot.py
python experiments/backwards_ablation/plot.py --mode healthy
python experiments/backwards_ablation/plot.py --out experiments/backwards_ablation/figs
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

ABLATION_DIR = Path(__file__).parent
DEFAULT_FIG_DIR = ABLATION_DIR / "figs"

from experiments.backwards_ablation.analyze import (  # noqa: E402
    DEFAULT_BACKWARD_DIR,
    DEFAULT_FORWARD_DIR,
    MODELS,
    _pair_on_seed,
    load_records,
)


def _mean_delta_and_ci(pairs: list[tuple[int, float, float]]) -> tuple[float, float, float] | None:
    if not pairs:
        return None
    from experiments.backwards_ablation.analyze import _bootstrap_ci
    diffs = [f - b for _, f, b in pairs]
    mean = sum(diffs) / len(diffs)
    lo, hi = _bootstrap_ci(diffs)
    return (mean, lo, hi)


def _bar_color(model: str) -> str:
    if model.startswith("claude"):
        return "#3b82f6"  # blue
    if model in {"deepseek-v3", "qwen-3.5"}:
        return "#10b981"  # green (open-source)
    if model == "heuristic":
        return "#9ca3af"  # grey (null control)
    return "#f97316"  # orange (GPT)


def plot_panel_a(
    mode: str, forward_dir: Path, backward_dir: Path, out_path: Path,
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    loaded = load_records(mode, forward_dir, backward_dir)
    entries: list[tuple[str, float, float, float]] = []  # (model, mean_delta, ci_lo, ci_hi)
    for model in MODELS:
        stat = _mean_delta_and_ci(_pair_on_seed(loaded[model]))
        if stat is None:
            continue
        entries.append((model, stat[0], stat[1], stat[2]))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if not entries:
        ax.text(
            0.5, 0.5, f"No paired data for '{mode}' mode yet.\nRun the sweep first.",
            ha="center", va="center", transform=ax.transAxes, fontsize=12,
        )
        ax.set_axis_off()
    else:
        xs = np.arange(len(entries))
        means = np.array([e[1] for e in entries])
        los = np.array([e[2] for e in entries])
        his = np.array([e[3] for e in entries])
        err_lo = means - los
        err_hi = his - means

        for i, (model, mean, _, _) in enumerate(entries):
            color = _bar_color(model)
            hatch = "///" if model == "heuristic" else None
            ax.bar(
                xs[i], mean, color=color, edgecolor="black",
                linewidth=0.7, hatch=hatch, zorder=2,
            )
        ax.errorbar(
            xs, means, yerr=[err_lo, err_hi],
            fmt="none", ecolor="black", capsize=3, linewidth=1, zorder=3,
        )
        ax.axhline(0, color="black", linewidth=0.7, linestyle="--", zorder=1)
        ax.set_xticks(xs)
        ax.set_xticklabels([e[0] for e in entries], rotation=30, ha="right")
        ax.set_ylabel("Paired Δ (forward − backward) composite score")
        ax.set_title(f"Panel A — Structural-prior reliance ({mode}, medium tier)")
        ax.grid(axis="y", alpha=0.3, zorder=0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_panel_b(
    mode: str, forward_dir: Path, backward_dir: Path, out_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    loaded = load_records(mode, forward_dir, backward_dir)

    fig, ax = plt.subplots(figsize=(6, 6))
    any_data = False
    for model in MODELS:
        pairs = _pair_on_seed(loaded[model])
        if not pairs:
            continue
        any_data = True
        xs = [f for _, f, _ in pairs]
        ys = [b for _, _, b in pairs]
        ax.scatter(xs, ys, s=22, alpha=0.7, edgecolor="none",
                   color=_bar_color(model), label=model)

    if not any_data:
        ax.text(
            0.5, 0.5, f"No paired data for '{mode}' mode yet.",
            ha="center", va="center", transform=ax.transAxes, fontsize=12,
        )
        ax.set_axis_off()
    else:
        ax.plot([0, 1], [0, 1], color="black", linewidth=0.7, linestyle="--", zorder=0)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Forward composite score")
        ax.set_ylabel("Backward composite score")
        ax.set_aspect("equal")
        ax.set_title(f"Panel B — Forward vs backward per seed ({mode}, medium)")
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
        ax.grid(alpha=0.3, zorder=0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _disease_subscore_delta(
    records: dict[str, list[dict]], key: str,
) -> list[tuple[int, float, float]]:
    """Pair forward/backward on seed and return (seed, fwd, bwd) for a sub-score."""
    fwd = {r["seed"]: r for r in records["forward"] if "error" not in r}
    bwd = {r["seed"]: r for r in records["backward"] if "error" not in r}
    pairs: list[tuple[int, float, float]] = []
    for seed in sorted(set(fwd) & set(bwd)):
        f = fwd[seed].get(key)
        b = bwd[seed].get(key)
        if f is None or b is None:
            continue
        pairs.append((seed, float(f), float(b)))
    return pairs


def plot_disease_subscores(
    forward_dir: Path, backward_dir: Path, out_path: Path,
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    loaded = load_records("disease", forward_dir, backward_dir)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    panel_titles = [
        ("avg_accuracy", "Prediction accuracy"),
        ("diagnosis_score", "Diagnosis score"),
        ("rescue_fraction", "Rescue fraction"),
    ]

    for ax, (key, title) in zip(axes, panel_titles):
        entries: list[tuple[str, float, float, float]] = []
        for model in MODELS:
            pairs = _disease_subscore_delta(loaded[model], key)
            if not pairs:
                continue
            stat = _mean_delta_and_ci(pairs)
            if stat is None:
                continue
            entries.append((model, stat[0], stat[1], stat[2]))

        if not entries:
            ax.text(
                0.5, 0.5, "No data yet", ha="center", va="center",
                transform=ax.transAxes, fontsize=10,
            )
            ax.set_axis_off()
            ax.set_title(title)
            continue

        xs = np.arange(len(entries))
        means = np.array([e[1] for e in entries])
        los = np.array([e[2] for e in entries])
        his = np.array([e[3] for e in entries])

        for i, (model, mean, _, _) in enumerate(entries):
            color = _bar_color(model)
            hatch = "///" if model == "heuristic" else None
            ax.bar(
                xs[i], mean, color=color, edgecolor="black",
                linewidth=0.7, hatch=hatch, zorder=2,
            )
        ax.errorbar(
            xs, means, yerr=[means - los, his - means],
            fmt="none", ecolor="black", capsize=3, linewidth=1, zorder=3,
        )
        ax.axhline(0, color="black", linewidth=0.7, linestyle="--", zorder=1)
        ax.set_xticks(xs)
        ax.set_xticklabels([e[0] for e in entries], rotation=30, ha="right", fontsize=8)
        ax.set_ylabel(f"Δ ({title})")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3, zorder=0)

    fig.suptitle("Disease-mode sub-scores — forward vs backward paired deltas (medium)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", action="append", choices=["healthy", "disease"])
    parser.add_argument("--forward-dir", type=Path, default=DEFAULT_FORWARD_DIR)
    parser.add_argument("--backward-dir", type=Path, default=DEFAULT_BACKWARD_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_FIG_DIR)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    modes = args.mode or ["healthy", "disease"]

    for mode in modes:
        plot_panel_a(mode, args.forward_dir, args.backward_dir, args.out / f"panel_a_delta_{mode}.png")
        plot_panel_b(mode, args.forward_dir, args.backward_dir, args.out / f"panel_b_scatter_{mode}.png")
        print(f"wrote {args.out}/panel_a_delta_{mode}.png, panel_b_scatter_{mode}.png")

    if "disease" in modes:
        plot_disease_subscores(args.forward_dir, args.backward_dir, args.out / "disease_subscores.png")
        print(f"wrote {args.out}/disease_subscores.png")


if __name__ == "__main__":
    main()
