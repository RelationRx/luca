"""
Paper v1 analysis script.

Reads session logs from logs/<sweep>/logs/*.json and produces analysis tables
for §4.3 (budget), §4.4 (disease/ambiguity), §4.5 (complexity threshold), §5 (strategy).

Usage:
    python experiments/paper_v1/analyse.py
    python experiments/paper_v1/analyse.py --section budget
    python experiments/paper_v1/analyse.py --section complexity
    python experiments/paper_v1/analyse.py --section disease
    python experiments/paper_v1/analyse.py --section strategy
    python experiments/paper_v1/analyse.py --section all
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LOGS_DIR = Path(__file__).parent / "logs"

SWEEPS = {
    "B_easy_healthy":   {"difficulty": "easy",   "disease": False},
    "A_medium_healthy": {"difficulty": "medium",  "disease": False},
    "B_hard_healthy":   {"difficulty": "hard",    "disease": False},
    "A_medium_disease": {"difficulty": "medium",  "disease": True},
}

LLM_MODELS = ["claude-opus-4-6", "claude-sonnet-4-6", "gpt-5.1", "gpt-4o", "gpt-4.1"]
ALL_MODELS  = LLM_MODELS  # heuristic/random have no logs

CANONICAL_SEEDS = set(range(20))  # seeds 0-19

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_logs() -> list[dict]:
    """Load all session logs and return a flat list of enriched records."""
    records = []
    for sweep, meta in SWEEPS.items():
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

            # Composite score
            pred_acc = s.get("avg_accuracy") or 0.0
            if meta["disease"]:
                hyp = s.get("malfunction_hypothesis") or {}
                diag = hyp.get("score") or 0.0
                rescues = s.get("rescue_results") or []
                rescue = max((r.get("restored_fraction", 0.0) for r in rescues), default=0.0)
                composite = statistics.mean([pred_acc, diag, rescue])
            else:
                composite = pred_acc
                diag = None
                rescue = None

            records.append({
                "sweep": sweep,
                "difficulty": meta["difficulty"],
                "disease": meta["disease"],
                "model": model,
                "seed": seed,
                # scores
                "composite": composite,
                "pred_acc": pred_acc,
                "avg_mse": s.get("avg_mse") or 0.0,
                "diagnosis_score": diag,
                "rescue_fraction": rescue,
                # budget
                "budget_used": s.get("budget_used") or 0,
                "budget_total": s.get("budget_total") or 31,
                "budget_frac": (s.get("budget_used") or 0) / (s.get("budget_total") or 31),
                "n_experiments": s.get("n_experiments") or 0,
                # disease extras
                "n_diag_alternatives": s.get("n_diagnosis_alternatives") or 0,
                # strategy
                "turns": log.get("turns", []),
                # network reconstruction
                "network_f1": (
                    (s.get("network_reconstruction") or {})
                    .get("undirected", {})
                    .get("f1")
                ),
            })
    return records


def filter_records(records, model=None, sweep=None, difficulty=None, disease=None):
    out = records
    if model:
        out = [r for r in out if r["model"] == model]
    if sweep:
        out = [r for r in out if r["sweep"] == sweep]
    if difficulty:
        out = [r for r in out if r["difficulty"] == difficulty]
    if disease is not None:
        out = [r for r in out if r["disease"] == disease]
    return out


def mean_std(values):
    if not values:
        return float("nan"), float("nan")
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return m, s


# ---------------------------------------------------------------------------
# §4.3 / §4.5 — Budget usage patterns
# ---------------------------------------------------------------------------

def analyse_budget(records):
    print("\n" + "=" * 70)
    print("BUDGET USAGE  (mean budget_frac ± std, N=20 per cell)")
    print("=" * 70)

    sweeps_h = ["B_easy_healthy", "A_medium_healthy", "B_hard_healthy", "A_medium_disease"]
    labels   = ["Easy", "Med(H)", "Hard", "Med(D)"]

    header = f"{'Model':<22}" + "".join(f"  {l:<12}" for l in labels)
    print(header)
    print("-" * len(header))

    for model in LLM_MODELS:
        row = f"{model:<22}"
        for sweep in sweeps_h:
            recs = filter_records(records, model=model, sweep=sweep)
            fracs = [r["budget_frac"] for r in recs]
            m, s = mean_std(fracs)
            row += f"  {m:.2f}±{s:.2f}    "
        print(row)

    # Zero-experiment seeds
    print("\nZero-experiment seeds (budget_used=0, typically 'lazy' sessions):")
    for model in LLM_MODELS:
        for sweep in sweeps_h:
            recs = filter_records(records, model=model, sweep=sweep)
            lazy = [r for r in recs if r["n_experiments"] == 0]
            if lazy:
                print(f"  {model:<22} {sweep:<22}  {len(lazy)}/{len(recs)} zero-experiment seeds")

    # Budget vs composite correlation on hard
    print("\nCorrelation: budget_frac vs composite on B_hard_healthy (per model):")
    for model in LLM_MODELS:
        recs = filter_records(records, model=model, sweep="B_hard_healthy")
        if len(recs) < 3:
            continue
        fracs = [r["budget_frac"] for r in recs]
        comps = [r["composite"] for r in recs]
        # Pearson r manually
        n = len(fracs)
        mf, mc = statistics.mean(fracs), statistics.mean(comps)
        cov = sum((f - mf) * (c - mc) for f, c in zip(fracs, comps)) / n
        sf = statistics.stdev(fracs) or 1e-9
        sc = statistics.stdev(comps) or 1e-9
        r = cov / (sf * sc)
        print(f"  {model:<22}  r = {r:+.3f}  (n={n})")


# ---------------------------------------------------------------------------
# §4.5 — Complexity threshold
# ---------------------------------------------------------------------------

def analyse_complexity(records):
    print("\n" + "=" * 70)
    print("COMPLEXITY THRESHOLD  (composite mean ± std, N=20)")
    print("=" * 70)

    sweeps_h = ["B_easy_healthy", "A_medium_healthy", "B_hard_healthy"]
    labels   = ["Easy", "Medium", "Hard", "Drop(E→H)"]

    header = f"{'Model':<22}" + "".join(f"  {l:<14}" for l in labels)
    print(header)
    print("-" * len(header))

    for model in LLM_MODELS + ["heuristic*", "random*"]:
        row = f"{model:<22}"
        means = []
        for sweep in sweeps_h:
            recs = filter_records(records, model=model.rstrip("*"), sweep=sweep)
            comps = [r["composite"] for r in recs]
            m, s = mean_std(comps)
            means.append(m)
            row += f"  {m:.3f}±{s:.3f}    "
        if len(means) == 3 and not any(m != m for m in means):
            row += f"  {means[0] - means[2]:+.3f}"
        print(row)

    # Per-seed variance as signal of bimodal distribution
    print("\nPer-seed composite std on hard (high std = bimodal, not gradual):")
    for model in LLM_MODELS:
        recs = filter_records(records, model=model, sweep="B_hard_healthy")
        comps = [r["composite"] for r in recs]
        _, s = mean_std(comps)
        n_high = sum(1 for c in comps if c >= 0.80)
        n_low  = sum(1 for c in comps if c < 0.50)
        print(f"  {model:<22}  std={s:.3f}  seeds≥0.80: {n_high}/20  seeds<0.50: {n_low}/20")


# ---------------------------------------------------------------------------
# §4.4 — Disease mode: diagnosis, rescue, ambiguity
# ---------------------------------------------------------------------------

def analyse_disease(records):
    print("\n" + "=" * 70)
    print("DISEASE MODE ANALYSIS  (A_medium_disease, N=20)")
    print("=" * 70)

    disease_recs = filter_records(records, sweep="A_medium_disease")

    # Main table
    print("\nModel breakdown:")
    header = f"  {'Model':<22}  {'PredAcc':>8}  {'Diag':>6}  {'Rescue':>7}  {'Composite':>9}  {'N':>3}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for model in LLM_MODELS:
        recs = filter_records(disease_recs, model=model)
        pred  = [r["pred_acc"] for r in recs]
        diag  = [r["diagnosis_score"] for r in recs]
        resc  = [r["rescue_fraction"] for r in recs]
        comp  = [r["composite"] for r in recs]
        print(f"  {model:<22}  {statistics.mean(pred):>8.3f}  "
              f"{statistics.mean(diag):>6.3f}  {statistics.mean(resc):>7.3f}  "
              f"{statistics.mean(comp):>9.3f}  {len(recs):>3}")

    # Prediction/diagnosis dissociation
    print("\nPrediction/diagnosis dissociation:")
    print("  (high pred_acc + low diagnosis = model forward-simulates but can't abduct)")
    for model in LLM_MODELS:
        recs = filter_records(disease_recs, model=model)
        dissociated = [r for r in recs if r["pred_acc"] >= 0.667 and (r["diagnosis_score"] or 0) == 0.0]
        print(f"  {model:<22}  {len(dissociated)}/20 seeds: good predictions, zero diagnosis")

    # Ambiguity analysis
    print("\nDiagnosis score by n_diagnosis_alternatives:")
    for n_alt in [0, 1, 2, 3]:
        recs_alt = [r for r in disease_recs if r["n_diag_alternatives"] == n_alt]
        if not recs_alt:
            continue
        by_model = {}
        for model in LLM_MODELS:
            m_recs = [r for r in recs_alt if r["model"] == model]
            if m_recs:
                by_model[model] = statistics.mean(r["diagnosis_score"] for r in m_recs)
        print(f"  n_alternatives={n_alt}  (N={len(recs_alt)} sessions)")
        for model, score in by_model.items():
            print(f"    {model:<22}  diag={score:.3f}")

    # Rescue vs diagnosis
    print("\nDoes diagnosis accuracy predict rescue success?")
    correct_diag   = [r for r in disease_recs if (r["diagnosis_score"] or 0) >= 1.0]
    incorrect_diag = [r for r in disease_recs if (r["diagnosis_score"] or 0) == 0.0]
    partial_diag   = [r for r in disease_recs if (r["diagnosis_score"] or 0) == 0.5]
    def rescue_mean(recs):
        vals = [r["rescue_fraction"] for r in recs if r["rescue_fraction"] is not None]
        return statistics.mean(vals) if vals else float("nan")
    print(f"  Correct diagnosis  (score=1.0, N={len(correct_diag)}):  rescue={rescue_mean(correct_diag):.3f}")
    print(f"  Partial diagnosis  (score=0.5, N={len(partial_diag)}):  rescue={rescue_mean(partial_diag):.3f}")
    print(f"  Wrong diagnosis    (score=0.0, N={len(incorrect_diag)}):  rescue={rescue_mean(incorrect_diag):.3f}")


# ---------------------------------------------------------------------------
# §5 — Strategy analysis
# ---------------------------------------------------------------------------

def _parse_experiments(turns):
    """Extract list of (intervention_type, n_genes) from turn tool calls."""
    expts = []
    for turn in turns:
        for tc in turn.get("tool_calls", []):
            if tc.get("tool") == "run_experiment" or tc.get("name") == "run_experiment":
                inp = tc.get("input", {})
                interventions = inp.get("interventions", {})
                if isinstance(interventions, dict):
                    types = set(v.get("type", "?") if isinstance(v, dict) else str(v)
                                for v in interventions.values())
                    expts.append({
                        "n_genes": len(interventions),
                        "types": types,
                        "is_single": len(interventions) == 1,
                        "is_multi": len(interventions) > 1,
                        "genes": list(interventions.keys()),
                    })
    return expts


def analyse_strategy(records):
    print("\n" + "=" * 70)
    print("STRATEGY ANALYSIS  (A_medium_healthy, N=20)")
    print("=" * 70)

    medium_recs = filter_records(records, sweep="A_medium_healthy")

    print(f"\n{'Model':<22}  {'AvgExpts':>8}  {'BudgetFrac':>10}  {'SingleGene%':>11}  {'MultiGene%':>10}  {'Coverage%':>10}")
    print("-" * 80)

    for model in LLM_MODELS:
        recs = filter_records(medium_recs, model=model)
        n_expts_list, single_pct_list, multi_pct_list, coverage_list = [], [], [], []

        for r in recs:
            expts = _parse_experiments(r["turns"])
            n = len(expts)
            n_expts_list.append(n)
            if n > 0:
                single_pct_list.append(sum(1 for e in expts if e["is_single"]) / n)
                multi_pct_list.append(sum(1 for e in expts if e["is_multi"]) / n)
                # coverage: unique genes BLOCKed
                genes_tested = set()
                for e in expts:
                    genes_tested.update(e["genes"])
                # approximate total genes from budget_total (20 genes per organism)
                coverage_list.append(min(len(genes_tested) / 20, 1.0))
            else:
                single_pct_list.append(0.0)
                multi_pct_list.append(0.0)
                coverage_list.append(0.0)

        print(f"{model:<22}  {statistics.mean(n_expts_list):>8.1f}  "
              f"{statistics.mean(r['budget_frac'] for r in recs):>10.2f}  "
              f"{statistics.mean(single_pct_list)*100:>10.1f}%  "
              f"{statistics.mean(multi_pct_list)*100:>9.1f}%  "
              f"{statistics.mean(coverage_list)*100:>9.1f}%")

    # Adaptive vs exhaustive: do models follow up on informative experiments?
    print("\nAdaptive behaviour (disease mode): % sessions where model tested")
    print("a gene more than once (suggests follow-up after initial BLOCK):")
    disease_recs = filter_records(records, sweep="A_medium_disease")
    for model in LLM_MODELS:
        recs = filter_records(disease_recs, model=model)
        adaptive = 0
        for r in recs:
            expts = _parse_experiments(r["turns"])
            all_genes = [g for e in expts for g in e["genes"]]
            if len(all_genes) != len(set(all_genes)):
                adaptive += 1
        print(f"  {model:<22}  {adaptive}/20 sessions with repeated gene testing")


# ---------------------------------------------------------------------------
# Network reconstruction correlation
# ---------------------------------------------------------------------------

def analyse_network(records):
    print("\n" + "=" * 70)
    print("NETWORK RECONSTRUCTION vs PREDICTION ACCURACY")
    print("=" * 70)

    for sweep in ["A_medium_healthy", "B_hard_healthy"]:
        recs_with_net = [r for r in records if r["sweep"] == sweep and r["network_f1"] is not None]
        print(f"\n{sweep}  (N with network_f1={len(recs_with_net)})")
        print(f"  {'Model':<22}  {'NetF1':>7}  {'PredAcc':>8}  {'r(F1,acc)':>10}")
        for model in LLM_MODELS:
            recs = [r for r in recs_with_net if r["model"] == model]
            if len(recs) < 3:
                continue
            f1s  = [r["network_f1"] for r in recs]
            accs = [r["pred_acc"]   for r in recs]
            mf1, _ = mean_std(f1s)
            mac, _ = mean_std(accs)
            n = len(recs)
            mf, mc = statistics.mean(f1s), statistics.mean(accs)
            cov = sum((f - mf) * (a - mc) for f, a in zip(f1s, accs)) / n
            sf = statistics.stdev(f1s) or 1e-9
            sa = statistics.stdev(accs) or 1e-9
            r_val = cov / (sf * sa)
            print(f"  {model:<22}  {mf1:>7.3f}  {mac:>8.3f}  {r_val:>10.3f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", default="all",
                        choices=["all", "budget", "complexity", "disease", "strategy", "network"])
    args = parser.parse_args()

    print("Loading logs...")
    records = load_all_logs()
    print(f"Loaded {len(records)} session records from {len(SWEEPS)} sweeps.")

    if args.section in ("all", "complexity"):
        analyse_complexity(records)
    if args.section in ("all", "budget"):
        analyse_budget(records)
    if args.section in ("all", "disease"):
        analyse_disease(records)
    if args.section in ("all", "strategy"):
        analyse_strategy(records)
    if args.section in ("all", "network"):
        analyse_network(records)


if __name__ == "__main__":
    main()
