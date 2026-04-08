#!/usr/bin/env python3
"""Harder regimes — heuristic systematic-sweep agent (no API key required).

Strategy (disease mode):
  1. KO sweep all visible genes (within budget headroom)
  2. OE sweep top-5 genes where KO was most detrimental (LOF candidates)
  3. Signal activation sweep
  4. Diagnose: best GOF = top KO-improver; best LOF = top OE-improver;
     chronic_signal heuristic: if best KO gene is a known signal target and
     activating that signal hurts, prefer the signal hypothesis
  5. Submit malfunction hypothesis
  6. Test rescue with corrective intervention (+ OE fallback for GOF)
  7. Predict tasks via additive single-gene approximation
  8. Submit free-text hypothesis summary

Results → results_heuristic.jsonl  (separate from LLM results.jsonl)

Usage:
    python run_heuristic_sweep.py
    python run_heuristic_sweep.py --dry-run
    python run_heuristic_sweep.py --arm A
    python run_heuristic_sweep.py --arm B
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from luca.generation import generate_disease_organism
from luca.experiment import ExperimentSession, recommended_budget

# ---------------------------------------------------------------------------
# Grid (same as run_sweep.py)
# ---------------------------------------------------------------------------

ARM_A = [
    (n, diff, seed, 1.0)
    for n in [75, 100]
    for diff in ["medium", "hard"]
    for seed in [0, 1, 2]
]

ARM_B = [
    (n, "hard", seed, mult)
    for n in [35, 50]
    for mult in [0.5, 0.75]
    for seed in [0, 1, 2]
]

FIXED = dict(n_modules=4, n_signals=3, n_phenotypes=3)

STUDY_DIR    = Path(__file__).resolve().parent
LOGS_DIR     = STUDY_DIR / "logs_heuristic"
RESULTS_PATH = STUDY_DIR / "results_heuristic.jsonl"


# ---------------------------------------------------------------------------
# Heuristic agent
# ---------------------------------------------------------------------------

def _improvement_score(
    phenos: dict[str, float],
    baseline: dict[str, float],
    aberrant: list[str],
    healthy_ranges: dict[str, list],
) -> float:
    """
    Score how much `phenos` improves on `baseline` for the aberrant phenotypes.
    Positive = closer to healthy range, negative = farther away.
    """
    score = 0.0
    for label in aberrant:
        base = baseline.get(label, 0.5)
        val  = phenos.get(label, base)
        lo, hi = healthy_ranges.get(label, [0.0, 1.0])

        def dist(v: float) -> float:
            if v < lo:
                return lo - v
            if v > hi:
                return v - hi
            return 0.0

        score += dist(base) - dist(val)   # positive = improvement
    return score


def run_heuristic_agent(
    session: ExperimentSession,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Run the systematic-sweep heuristic agent on a disease ExperimentSession.
    Returns session.get_summary() after all tasks completed.
    """
    # ── Phase 0: organism info ────────────────────────────────────────────
    info           = session.get_info()
    gene_names     = info["gene_names"]
    signals        = info["signals"]            # [{"label": ..., "mode": ...}]
    pheno_labels   = info["observable_phenotypes"]
    baseline       = info["baseline_phenotypes"]
    aberrant       = info.get("aberrant_phenotypes", [])
    healthy_ranges = info.get("healthy_phenotype_ranges", {})

    # Build signal-target map from organism (for chronic_signal heuristic)
    # signal label → list of gene names it targets
    org = session.organism
    gene_id_to_name = {g.id: g.name for g in org.genes}
    signal_targets: dict[str, list[str]] = {
        s.label: [gene_id_to_name.get(t, t) for t in s.targets]
        for s in org.signals
    }

    def score(phenos: dict) -> float:
        return _improvement_score(phenos, baseline, aberrant, healthy_ranges)

    # Budget headroom: reserve slots for OE, signals, rescue, predictions
    RESERVE = max(6, int(0.15 * session.budget))

    def budget_ok(extra: int = 1) -> bool:
        return session.budget_used + extra <= session.budget - RESERVE

    # Accumulated single-intervention data for prediction tasks
    # (gene_name, iv_type) → {phenotype: value}
    measured: dict[tuple, dict[str, float]] = {}

    # ── Phase 1: BLOCK sweep ─────────────────────────────────────────────
    ko_scores: dict[str, float] = {}
    for gene in gene_names:
        if not budget_ok():
            break
        result = session.run_experiment({gene: {"type": "BLOCK"}})
        if "error" in result:
            continue
        phenos = result["phenotypes"]
        ko_scores[gene] = score(phenos)
        measured[(gene, "BLOCK")] = phenos
        if verbose:
            print(f"    BLOCK {gene:>6}: score={ko_scores[gene]:+.3f}")

    ko_ranked = sorted(ko_scores.items(), key=lambda x: x[1], reverse=True)

    # ── Phase 2: BOOST sweep — top-5 genes where BLOCK was most detrimental ──
    oe_scores: dict[str, float] = {}
    lof_candidates = [g for g, s in ko_ranked if s < 0][:5]
    for gene in lof_candidates:
        if not budget_ok():
            break
        result = session.run_experiment({gene: {"type": "BOOST"}})
        if "error" in result:
            continue
        phenos = result["phenotypes"]
        oe_scores[gene] = score(phenos)
        measured[(gene, "BOOST")] = phenos
        if verbose:
            print(f"    BOOST {gene:>6}: score={oe_scores[gene]:+.3f}")

    # ── Phase 3: Signal activation sweep ─────────────────────────────────
    sig_scores: dict[str, float] = {}
    for sig in signals:
        if not budget_ok():
            break
        result = session.run_experiment({sig["label"]: "activate"})
        if "error" in result:
            continue
        phenos = result["phenotypes"]
        sig_scores[sig["label"]] = score(phenos)
        if verbose:
            print(f"    ACT {sig['label']:>12}: score={sig_scores[sig['label']]:+.3f}")

    # ── Phase 4: Diagnosis ────────────────────────────────────────────────
    best_gof_gene  = ko_ranked[0][0]  if ko_ranked  else None
    best_gof_score = ko_ranked[0][1]  if ko_ranked  else -999.0
    best_lof_gene  = max(oe_scores, key=oe_scores.get) if oe_scores else None
    best_lof_score = oe_scores[best_lof_gene] if best_lof_gene else -999.0

    # Chronic-signal heuristic:
    #   If the best GOF candidate is a target of some signal, AND
    #   activating that signal has a negative score (already saturated),
    #   prefer the chronic_signal hypothesis for that signal.
    chronic_candidate: str | None = None
    chronic_score: float = -999.0
    if best_gof_gene:
        for sig_label, targets in signal_targets.items():
            if best_gof_gene in targets:
                act_score = sig_scores.get(sig_label, 999.0)
                if act_score <= 0.0:   # activating it didn't help → already active
                    if -act_score > chronic_score:
                        chronic_score = -act_score
                        chronic_candidate = sig_label

    # Choose best hypothesis
    candidates = []
    if best_gof_gene  and best_gof_score  > 0: candidates.append((best_gof_score,  best_gof_gene,       "LOCK_HI"))
    if best_lof_gene  and best_lof_score  > 0: candidates.append((best_lof_score,  best_lof_gene,       "LOCK_LO"))
    if chronic_candidate and chronic_score > 0: candidates.append((chronic_score,   chronic_candidate,   "PERSIST"))

    if candidates:
        candidates.sort(reverse=True)
        _, hyp_target, hyp_type = candidates[0]
    else:
        # Fallback: best BLOCK gene as LOCK_HI regardless of score
        hyp_target = best_gof_gene or (gene_names[0] if gene_names else "unknown")
        hyp_type   = "LOCK_HI"

    # ── Phase 5: Submit hypothesis ────────────────────────────────────────
    session.submit_malfunction_hypothesis(hyp_target, hyp_type)

    # ── Phase 6: Test rescue ──────────────────────────────────────────────
    if hyp_type == "LOCK_HI":
        primary_rescue = {hyp_target: {"type": "BLOCK"}}
    elif hyp_type == "LOCK_LO":
        primary_rescue = {hyp_target: {"type": "BOOST"}}
    else:  # PERSIST — BLOCK the downstream target gene as proxy
        proxy_gene = best_gof_gene or (gene_names[0] if gene_names else None)
        primary_rescue = {proxy_gene: {"type": "BLOCK"}} if proxy_gene else {}

    if primary_rescue and session.budget_used < session.budget:
        rescue_result = session.test_rescue(primary_rescue)
        if verbose:
            print(f"    Rescue ({hyp_type}): restored={rescue_result.get('restored_fraction', 0):.0%}")

    # ── Phase 7: Prediction tasks ─────────────────────────────────────────
    # Additive approximation: predicted = baseline + Σ single-gene deltas
    while True:
        task = session.get_next_prediction_task()
        if task.get("done"):
            break
        task_id      = task["task_id"]
        interventions = task["interventions"]   # {gene_name: {"type": ...}}

        prediction: dict[str, float] = {}
        for ph in pheno_labels:
            base        = baseline.get(ph, 0.5)
            total_delta = 0.0
            for gene, iv in interventions.items():
                iv_type = iv["type"] if isinstance(iv, dict) else str(iv)
                key = (gene, iv_type)
                if key in measured:
                    total_delta += measured[key].get(ph, base) - base
                # Unmeasured: assume no effect (delta = 0)
            prediction[ph] = float(np.clip(base + total_delta, 0.0, 1.0))

        session.submit_prediction(task_id, prediction)
        if verbose:
            print(f"    Predict {task_id}: {prediction}")

    # ── Phase 8: Submit hypothesis text ──────────────────────────────────
    ko_n     = len(ko_scores)
    oe_n     = len(oe_scores)
    sig_n    = len(sig_scores)
    top_score = ko_ranked[0][1] if ko_ranked else 0.0
    hyp_text = (
        f"Systematic sweep: BLOCKed {ko_n} nodes (top score {top_score:+.3f}), "
        f"BOOSTed {oe_n} LOCK_LO candidates, activated {sig_n} signals. "
        f"Hypothesis: {hyp_type} of {hyp_target}. "
        f"Prediction: additive single-node approximation."
    )
    session.submit_hypothesis(hyp_text)

    return session.get_summary()


# ---------------------------------------------------------------------------
# Metrics extraction
# ---------------------------------------------------------------------------

def extract_metrics(
    summary: dict,
    org,
    n: int,
    diff: str,
    seed: int,
    mult: float,
) -> dict:
    mh = summary.get("malfunction_hypothesis")
    rr = summary.get("rescue_results", [])
    m0 = org.malfunctions[0] if org.malfunctions else None
    return {
        "agent":                   "heuristic_sweep",
        "arm":                     "A" if mult == 1.0 else "B",
        "n_genes":                 n,
        "difficulty":              diff,
        "seed":                    seed,
        "budget_multiplier":       mult,
        "budget_total":            summary.get("budget_total"),
        "budget_used":             summary.get("budget_used"),
        "n_experiments":           summary.get("n_experiments", 0),
        "malfunction_type":        m0.type        if m0 else None,
        "malfunction_target":      m0.target_name if m0 else None,
        "n_latent":                len(org.latent_genes),
        "malfunction_score":       mh["score"]    if mh else None,
        "n_rescue_attempts":       len(rr),
        "best_rescue_fraction":    max((r["restored_fraction"] for r in rr), default=None),
        "avg_prediction_accuracy": summary.get("avg_accuracy"),
        "avg_prediction_mse":      summary.get("avg_mse"),
    }


def already_recorded(n: int, diff: str, seed: int, mult: float) -> bool:
    if not RESULTS_PATH.exists():
        return False
    for line in RESULTS_PATH.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("n_genes") == n and r.get("difficulty") == diff
                and r.get("seed") == seed and r.get("budget_multiplier") == mult):
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LUCA harder_regimes heuristic sweep")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arm", choices=["A", "B"], default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    grid: list[tuple] = []
    if args.arm in (None, "A"):
        grid += [("A", *c) for c in ARM_A]
    if args.arm in (None, "B"):
        grid += [("B", *c) for c in ARM_B]

    total = len(grid)

    # Pre-generate organisms (cheap, no API calls)
    print("Generating organisms...")
    orgs: dict = {}
    for arm, n, diff, seed, mult in grid:
        key = (n, diff, seed)
        if key not in orgs:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                orgs[key] = generate_disease_organism(
                    n_genes=n, difficulty=diff, seed=seed, **FIXED
                )

    n_new = sum(1 for _, n, d, s, m in grid if not already_recorded(n, d, s, m))
    print(f"\n{total} conditions — {n_new} new runs  (agent: heuristic_sweep)\n")

    print(f"  {'#':>3}  {'arm'}  {'n':>4}  {'diff':<8}  {'s'}  {'mult':>6}  "
          f"{'budget':>6}  {'latent':>6}  malfunction")
    print("  " + "─" * 70)
    for idx, (arm, n, diff, seed, mult) in enumerate(grid, 1):
        org    = orgs[(n, diff, seed)]
        rec    = recommended_budget(org)
        budget = max(5, round(rec * mult))
        m0     = org.malfunctions[0] if org.malfunctions else None
        done   = already_recorded(n, diff, seed, mult)
        flag   = "  [skip]" if done else ""
        print(
            f"  {idx:>3}  {arm}    {n:>4}  {diff:<8}  {seed}  {mult:.2f}x  "
            f"{budget:>6}  {len(org.latent_genes):>6}  "
            f"{m0.type+'/'+m0.target_name if m0 else 'none'}{flag}"
        )

    if args.dry_run:
        return

    print()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    completed = skipped = 0

    for idx, (arm, n, diff, seed, mult) in enumerate(grid, 1):
        if already_recorded(n, diff, seed, mult):
            skipped += 1
            print(f"[{idx:>2}/{total}] SKIP  n={n}  {diff}  s={seed}  {mult:.2f}x")
            continue

        org    = orgs[(n, diff, seed)]
        rec    = recommended_budget(org)
        budget = max(5, round(rec * mult))
        m0     = org.malfunctions[0] if org.malfunctions else None

        print(
            f"[{idx:>2}/{total}] n={n:>3}  {diff:<8}  s={seed}  {mult:.2f}x  "
            f"budget={budget}  latent={len(org.latent_genes)}  "
            f"{m0.type+'/'+m0.target_name if m0 else 'none'}"
        )

        session = ExperimentSession(org, budget=budget, seed=seed)
        summary = run_heuristic_agent(session, verbose=args.verbose)
        record  = extract_metrics(summary, org, n, diff, seed, mult)

        diag   = record["malfunction_score"]
        rescue = record["best_rescue_fraction"]
        pred   = record["avg_prediction_accuracy"]
        bu     = record["budget_used"]
        bt     = record["budget_total"]

        print(
            f"       → diag={diag}  rescue={rescue}  "
            f"pred={pred}  used={bu}/{bt}"
        )

        with open(RESULTS_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
        completed += 1

    print(f"\nDone. Completed={completed}  Skipped={skipped}")
    print(f"Results → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
