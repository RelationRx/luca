"""LEMONS demo — full agent session.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python demo.py
"""
import json
import sys

from bioworld import generate_organism, ExperimentSession
from bioworld.agent import run_agent


def smoke_test() -> None:
    """Quick sanity checks without API calls."""
    print("=== Smoke Test ===")

    # 1. Generate organism
    from bioworld import generate_organism
    org = generate_organism(seed=0)
    print(f"Organism ID: {org.id}")
    print(f"  Genes: {len(org.genes)}")
    print(f"  Modules: {len(org.modules)}")
    print(f"  Signals: {len(org.signals)}")
    print(f"  Phenotypes: {len(org.phenotypes)}")
    print(f"  Observable genes: {len(org.observable_genes)}/{len(org.genes)}")

    # 2. JSON round-trip
    json_str = org.to_json()
    org2 = type(org).from_json(json_str)
    assert org.id == org2.id, "JSON round-trip failed"
    print("  JSON round-trip: OK")

    # 3. KO upstream gene changes phenotype
    from bioworld.dynamics import simulate_sigmoid
    import numpy as np

    baseline_phenos = {}
    from bioworld.dynamics import compute_phenotypes
    baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)

    # KO the first gene and check if phenotype changes
    first_gene = org.genes[0].id
    ko_result = simulate_sigmoid(
        org,
        interventions={first_gene: {"type": "KO"}},
        active_signals={},
        rng=np.random.default_rng(42),
    )
    ko_phenos = ko_result["phenotypes"]
    print(f"  Baseline phenotypes: {json.dumps({k: round(v,3) for k,v in baseline_phenos.items()})}")
    print(f"  KO({org.genes[0].name}) phenotypes: {json.dumps({k: round(v,3) for k,v in ko_phenos.items()})}")
    diffs = {k: round(abs(ko_phenos[k] - baseline_phenos[k]), 3) for k in baseline_phenos}
    print(f"  Phenotype diffs: {json.dumps(diffs)}")

    # 4. Module ARI: random vs ground truth
    from bioworld import ExperimentSession
    session = ExperimentSession(org, budget=20, seed=42)

    # Random assignment
    import random
    rng = random.Random(99)
    random_assignment = {
        g.name: rng.choice([m.label for m in org.modules])
        for g in org.genes
    }
    rand_result = session.submit_module_assignment(random_assignment)
    print(f"  Random module ARI={rand_result['ari']:.3f}, NMI={rand_result['nmi']:.3f}")

    # Ground truth assignment
    gt_assignment = {
        g.name: next(m.label for m in org.modules if g.id in m.gene_ids)
        for g in org.genes
    }
    gt_result = session.submit_module_assignment(gt_assignment)
    print(f"  GT module ARI={gt_result['ari']:.3f}, NMI={gt_result['nmi']:.3f}")
    assert gt_result["ari"] > 0.99, f"GT ARI should be ~1.0, got {gt_result['ari']}"

    # 5. Dataset generation
    from bioworld import generate_dataset
    paths = generate_dataset(
        n_organisms=3,
        experiments_per_organism=2,
        output_path="/tmp/bioworld_test_dataset",
        seed=7,
    )
    import os
    assert os.path.exists(paths["organisms"]), "organisms.json not found"
    assert os.path.exists(paths["experiments"]), "experiments.json not found"
    with open(paths["organisms"]) as f:
        orgs = json.load(f)
    with open(paths["experiments"]) as f:
        exps = json.load(f)
    assert len(orgs) == 3, f"Expected 3 organisms, got {len(orgs)}"
    assert len(exps) == 6, f"Expected 6 experiments, got {len(exps)}"
    # Check organism IDs are consistent
    org_ids = {o["id"] for o in orgs}
    exp_org_ids = {e["organism_id"] for e in exps}
    assert exp_org_ids <= org_ids, "Experiment organism IDs not in organisms"
    print(f"  Dataset: {len(orgs)} organisms, {len(exps)} experiments — IDs consistent: OK")

    print("\n=== All smoke tests passed! ===\n")


def agent_demo() -> None:
    """Run the full Claude agent on a BioWorld session."""
    print("=== Agent Demo ===")
    org = generate_organism(n_genes=15, n_modules=3, seed=42)
    session = ExperimentSession(org, budget=15, seed=42)
    summary = run_agent(session, model="claude-opus-4-6", max_turns=40, verbose=True)
    print("\nFinal summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    smoke_test()

    if "--agent" in sys.argv:
        agent_demo()
    else:
        print("Run with --agent to execute a full Claude agent session.")
        print("(Requires ANTHROPIC_API_KEY environment variable)")
