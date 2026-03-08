"""LEMONOIDS demo — full agent session.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python demo.py
"""
import json
import sys

from lemonoids import generate_organism, generate_disease_organism, ExperimentSession
from lemonoids.agent import run_agent


def smoke_test() -> None:
    """Quick sanity checks without API calls."""
    print("=== Smoke Test ===")

    # 1. Generate organism
    from lemonoids import generate_organism
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

    # 3. BLOCK upstream gene changes phenotype
    from lemonoids.dynamics import simulate_sigmoid
    import numpy as np

    baseline_phenos = {}
    from lemonoids.dynamics import compute_phenotypes
    baseline_phenos = compute_phenotypes(org, org.baseline_state, noise=False)

    # BLOCK the first gene and check if phenotype changes
    first_gene = org.genes[0].id
    block_result = simulate_sigmoid(
        org,
        interventions={first_gene: {"type": "BLOCK"}},
        active_signals={},
        rng=np.random.default_rng(42),
    )
    block_phenos = block_result["phenotypes"]
    print(f"  Baseline phenotypes: {json.dumps({k: round(v,3) for k,v in baseline_phenos.items()})}")
    print(f"  BLOCK({org.genes[0].name}) phenotypes: {json.dumps({k: round(v,3) for k,v in block_phenos.items()})}")
    diffs = {k: round(abs(block_phenos[k] - baseline_phenos[k]), 3) for k in baseline_phenos}
    print(f"  Phenotype diffs: {json.dumps(diffs)}")

    # 4. Dataset generation
    from lemonoids import generate_dataset
    paths = generate_dataset(
        n_organisms=3,
        experiments_per_organism=2,
        output_path="/tmp/lemonoids_test_dataset",
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


def disease_smoke_test() -> None:
    """Smoke test for the disease biology extension."""
    print("=== Disease Smoke Test ===")

    from lemonoids import generate_disease_organism
    from lemonoids.dynamics import compute_phenotypes

    org = generate_disease_organism(seed=7)
    assert org.cell_type is not None, "cell_type should be set"
    assert len(org.malfunctions) >= 1, "at least one malfunction expected"
    assert org.healthy_baseline != {}, "healthy_baseline should be non-empty"

    # At least one phenotype should be aberrant
    disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    aberrant = [
        label for label, val in disease_phenos.items()
        if not (org.healthy_phenotype_ranges[label][0] <= val <= org.healthy_phenotype_ranges[label][1])
    ]
    assert len(aberrant) >= 1, "No aberrant phenotypes — malfunction had no effect"

    # JSON round-trip preserves disease fields
    org2 = type(org).from_json(org.to_json())
    assert org2.cell_type is not None and org2.cell_type.label == org.cell_type.label
    assert len(org2.malfunctions) == len(org.malfunctions)
    assert org2.healthy_phenotype_ranges != {}
    print("  JSON round-trip (disease): OK")

    # ExperimentSession disease API
    session = ExperimentSession(org, budget=10, seed=7)
    info = session.get_info()
    assert "aberrant_phenotypes" in info, "aberrant_phenotypes missing from get_info()"
    assert "healthy_phenotype_ranges" in info, "healthy_phenotype_ranges missing from get_info()"

    # submit_malfunction_hypothesis first (required before test_rescue)
    first_gene = org.genes[0].name
    hyp = session.submit_malfunction_hypothesis("G999", "LOCK_HI")
    assert hyp.get("stored") is True, f"submit_malfunction_hypothesis returned: {hyp}"

    # test_rescue: pick first gene and BLOCK it — just checks the API works
    rescue = session.test_rescue({first_gene: {"type": "BLOCK"}})
    assert "restored_fraction" in rescue, f"test_rescue returned: {rescue}"
    assert "mse_vs_healthy" in rescue

    summary = session.get_summary()
    assert "malfunction_hypothesis" in summary
    assert "rescue_results" in summary

    print(f"  Cell type: {org.cell_type.label}")
    print(f"  Malfunctions: {[m.description for m in org.malfunctions]}")
    print(f"  Aberrant phenotypes: {aberrant}")
    print(f"  Rescue test (BLOCK {first_gene}): restored={rescue['restored_fraction']:.2f}, "
          f"mse={rescue['mse_vs_healthy']:.4f}")
    print("  Disease smoke test: OK")


def agent_demo() -> None:
    """Run the full Claude agent on a Lemonoids session."""
    print("=== Agent Demo ===")
    org = generate_organism(n_genes=15, n_modules=3, seed=42)
    session = ExperimentSession(org, budget=15, seed=42)
    summary = run_agent(session, model="claude-opus-4-6", max_turns=40, verbose=True)
    print("\nFinal summary:")
    print(json.dumps(summary, indent=2))


def disease_agent_demo() -> None:
    """Run the Claude agent on a disease organism session."""
    print("=== Disease Agent Demo ===")
    org = generate_disease_organism(n_genes=15, n_modules=3, seed=42)
    session = ExperimentSession(org, budget=15, seed=42)
    summary = run_agent(session, model="claude-opus-4-6", max_turns=40, verbose=True)
    print("\nFinal summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    smoke_test()
    disease_smoke_test()

    if "--agent" in sys.argv:
        if "--disease" in sys.argv:
            disease_agent_demo()
        else:
            agent_demo()
    else:
        print("Run with --agent to execute a full Claude agent session.")
        print("Run with --agent --disease for the disease biology agent session.")
        print("(Requires ANTHROPIC_API_KEY environment variable)")
