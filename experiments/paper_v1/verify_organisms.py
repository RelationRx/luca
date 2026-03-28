"""
Organism verification and difficulty characterisation.

For each seed × difficulty, runs three checks:

1. STRUCTURAL CHECK
   Verifies the generated organism has the expected structural properties
   (latent gene fraction, n_genes, n_phenotypes) per DIFFICULTY_PRESETS.

2. ADDITIVITY CHECK
   For each prediction task, computes an additive prediction from noiseless
   single-gene BLOCK effects and tests whether it falls within ±0.10 of
   ground truth for all phenotypes. If *all* tasks are additively solvable,
   the organism is functionally too easy for its tier — no causal reasoning
   required.

3. LATENT GENE RELEVANCE CHECK (hard tier only)
   Verifies at least one latent gene has a measurable effect on at least one
   phenotype. Latent genes that are fully disconnected from phenotypes are
   irrelevant confounders that don't add genuine difficulty.

Output: a summary table + per-seed JSONL file.

Usage
-----
    python experiments/paper_v1/verify_organisms.py
    python experiments/paper_v1/verify_organisms.py --difficulty hard
    python experiments/paper_v1/verify_organisms.py --seeds 0:20 --difficulty hard
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lemonoids import generate_organism, ExperimentSession           # noqa: E402
from lemonoids.dynamics import simulate_sigmoid, compute_phenotypes  # noqa: E402
from lemonoids.generation import DIFFICULTY_PRESETS                  # noqa: E402

ACCURACY_THRESHOLD = 0.10   # same threshold used in scoring


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------

def _noiseless_phenotypes(org, interventions: dict) -> dict[str, float]:
    """Run simulate_sigmoid with a fixed rng seed, then recompute phenotypes noise-free."""
    result = simulate_sigmoid(
        org,
        interventions=interventions,
        active_signals={},
        rng=np.random.default_rng(0),
    )
    return compute_phenotypes(org, result["final_state"], rng=np.random.default_rng(0), noise=False)


def _noiseless_single_gene_effects(
    org,
    baseline: dict[str, float],
    ph_labels: list[str],
) -> dict[str, dict[str, float]]:
    """
    Compute noiseless phenotype delta for BLOCKing each observable gene.
    Returns {gene_name: {ph_label: delta}}.
    """
    effects: dict[str, dict[str, float]] = {}
    latent = set(org.latent_genes)

    for gene in org.genes:
        if gene.id in latent:
            continue
        phenotypes = _noiseless_phenotypes(org, {gene.id: {"type": "BLOCK"}})
        effects[gene.name] = {
            ph: phenotypes.get(ph, baseline[ph]) - baseline[ph]
            for ph in ph_labels
        }
    return effects


def check_additivity(
    session: ExperimentSession,
    effects: dict[str, dict[str, float]],
    baseline: dict[str, float],
) -> dict:
    """
    For each prediction task, test whether the additive model (sum of
    single-gene BLOCK/BOOST effects) predicts within ±0.10 of ground truth.

    Returns dict with per-task results and summary flags.
    """
    ph_labels = list(baseline.keys())
    task_results = []

    for task_id, task in session._tasks.items():
        # Build additive prediction
        additive = dict(baseline)
        for gene_name, iv in task.interventions.items():
            iv_type = iv.get("type", "BLOCK") if isinstance(iv, dict) else iv
            sign = -1.0 if iv_type == "BLOCK" else 1.0
            gene_effects = effects.get(gene_name, {})
            for ph in ph_labels:
                additive[ph] = additive[ph] + sign * gene_effects.get(ph, 0.0)
                additive[ph] = max(0.0, min(1.0, additive[ph]))

        gt = task.ground_truth
        errors = {ph: abs(additive[ph] - gt.get(ph, 0.5)) for ph in ph_labels}
        within_threshold = all(e <= ACCURACY_THRESHOLD for e in errors.values())
        max_error = max(errors.values())

        task_results.append({
            "task_id": task_id,
            "interventions": {
                g: (iv.get("type") if isinstance(iv, dict) else iv)
                for g, iv in task.interventions.items()
            },
            "max_additive_error": round(max_error, 4),
            "additively_solvable": within_threshold,
        })

    all_solvable = all(t["additively_solvable"] for t in task_results)
    any_solvable = any(t["additively_solvable"] for t in task_results)

    return {
        "tasks": task_results,
        "n_tasks": len(task_results),
        "n_additively_solvable": sum(t["additively_solvable"] for t in task_results),
        "all_additively_solvable": all_solvable,
        "any_additively_solvable": any_solvable,
        "mean_max_error": round(
            sum(t["max_additive_error"] for t in task_results) / max(len(task_results), 1), 4
        ),
    }


def check_latent_relevance(
    org,
    baseline: dict[str, float],
    ph_labels: list[str],
    threshold: float = 0.05,
) -> dict:
    """
    For each latent gene, compute its noiseless BLOCK effect on phenotypes.
    A latent gene is 'relevant' if it shifts any phenotype by > threshold.
    """
    latent = set(org.latent_genes)
    gene_id_to_name = {g.id: g.name for g in org.genes}
    results = []

    for gene in org.genes:
        if gene.id not in latent:
            continue
        phenotypes = _noiseless_phenotypes(org, {gene.id: {"type": "BLOCK"}})
        shifts = {
            ph: abs(phenotypes.get(ph, baseline[ph]) - baseline[ph])
            for ph in ph_labels
        }
        relevant = any(s > threshold for s in shifts.values())
        results.append({
            "gene": gene_id_to_name[gene.id],
            "max_shift": round(max(shifts.values()), 4),
            "relevant": relevant,
        })

    n_relevant = sum(r["relevant"] for r in results)
    return {
        "n_latent": len(results),
        "n_latent_relevant": n_relevant,
        "all_latent_irrelevant": len(results) > 0 and n_relevant == 0,
        "latent_genes": results,
    }


def verify_organism(seed: int, difficulty: str) -> dict:
    """Run all verification checks on one organism. Returns a summary dict."""
    preset = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS["medium"])

    try:
        org = generate_organism(seed=seed, difficulty=difficulty)
    except Exception as e:
        return {"seed": seed, "difficulty": difficulty, "error": str(e)}

    try:
        session = ExperimentSession(org, seed=seed)
    except Exception as e:
        return {"seed": seed, "difficulty": difficulty, "error": f"session: {e}"}

    ph_labels = list(session.get_info()["baseline_phenotypes"].keys())
    baseline = session.get_info()["baseline_phenotypes"]

    # 1. Structural check
    n_latent_actual = len(org.latent_genes)
    n_latent_expected = round(preset["latent_fraction"] * len(org.genes))
    structural_ok = (
        len(org.genes) == 20  # canonical N
        and n_latent_actual == n_latent_expected
        and len(org.phenotypes) == 3
    )

    # 2. Noiseless single-gene effects (used by both additivity + latent checks)
    effects = _noiseless_single_gene_effects(org, baseline, ph_labels)

    # 3. Additivity check
    additivity = check_additivity(session, effects, baseline)

    # 4. Latent relevance (only meaningful for hard tier)
    latent = check_latent_relevance(org, baseline, ph_labels) if org.latent_genes else {
        "n_latent": 0, "n_latent_relevant": 0, "all_latent_irrelevant": False, "latent_genes": []
    }

    # 5. Observable gene coverage — what fraction of genes have any phenotype effect
    genes_with_effect = sum(
        1 for g, effs in effects.items()
        if any(abs(d) > 0.05 for d in effs.values())
    )
    coverage = genes_with_effect / max(len(effects), 1)

    # Verdict
    flags = []
    if additivity["all_additively_solvable"]:
        flags.append("ALL_TASKS_ADDITIVE")
    if latent["all_latent_irrelevant"] and org.latent_genes:
        flags.append("LATENT_GENES_IRRELEVANT")
    if coverage < 0.3:
        flags.append("LOW_GENE_COVERAGE")
    if not structural_ok:
        flags.append("STRUCTURAL_MISMATCH")

    return {
        "seed": seed,
        "difficulty": difficulty,
        "n_genes": len(org.genes),
        "n_observable": len(org.observable_genes),
        "n_latent": n_latent_actual,
        "n_phenotypes": len(org.phenotypes),
        "n_relations": len(org.relations),
        "structural_ok": structural_ok,
        "additivity": additivity,
        "latent_relevance": latent,
        "gene_coverage": round(coverage, 3),
        "flags": flags,
        "pass": len(flags) == 0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--difficulty", default=None,
                        help="Tier to verify: easy, medium, hard (default: all)")
    parser.add_argument("--seeds", default="0:20",
                        help="Seed range, e.g. 0:20 or 0 1 2 3 (default: 0:20)")
    args = parser.parse_args()

    # Parse seeds
    if ":" in args.seeds:
        a, b = args.seeds.split(":")
        seeds = list(range(int(a), int(b)))
    else:
        seeds = [int(s) for s in args.seeds.split()]

    difficulties = [args.difficulty] if args.difficulty else ["easy", "medium", "hard"]

    all_records = []

    for difficulty in difficulties:
        print(f"\n{'='*60}")
        print(f"Verifying {difficulty.upper()} organisms (seeds {seeds[0]}–{seeds[-1]})")
        print(f"{'='*60}")
        print(f"  {'Seed':>4}  {'Add-tasks':>10}  {'Latent-rel':>11}  {'Coverage':>9}  {'Flags'}")
        print(f"  {'-'*60}")

        for seed in seeds:
            r = verify_organism(seed, difficulty)
            all_records.append(r)

            if "error" in r:
                print(f"  {seed:>4}  ERROR: {r['error']}")
                continue

            add = r["additivity"]
            lat = r["latent_relevance"]
            add_str = f"{add['n_additively_solvable']}/{add['n_tasks']}"
            lat_str = f"{lat['n_latent_relevant']}/{lat['n_latent']}" if lat["n_latent"] else "n/a"
            flags_str = ", ".join(r["flags"]) if r["flags"] else "ok"
            marker = " ⚠" if r["flags"] else ""
            print(f"  {seed:>4}  {add_str:>10}  {lat_str:>11}  {r['gene_coverage']:>9.2f}  {flags_str}{marker}")

        # Summary
        tier_records = [r for r in all_records if r.get("difficulty") == difficulty and "error" not in r]
        n_fail = sum(1 for r in tier_records if not r["pass"])
        n_additive = sum(1 for r in tier_records if r["additivity"]["all_additively_solvable"])
        n_latent_irrel = sum(1 for r in tier_records if r["latent_relevance"]["all_latent_irrelevant"])
        print(f"\n  Summary: {n_fail}/{len(tier_records)} organisms flagged")
        print(f"    All tasks additive (too easy): {n_additive}")
        if difficulty == "hard":
            print(f"    Latent genes all irrelevant:   {n_latent_irrel}")

    # Save
    out_path = Path(__file__).parent / "organism_verification.jsonl"
    with open(out_path, "w") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")
    print(f"\nFull results → {out_path}")


if __name__ == "__main__":
    main()
