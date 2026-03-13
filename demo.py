"""LEMONOIDS demo — walks through the benchmark step by step.

Usage:
    python demo.py                        # walkthrough + sanity checks
    python demo.py --agent                # run an LLM agent (requires OPENAI_API_KEY or ANTHROPIC_API_KEY)
    python demo.py --agent --disease      # disease mode agent session
    python demo.py --model gpt-4o         # choose model (default: gpt-4o)
"""
import json
import sys

from lemonoids import generate_organism, generate_disease_organism, ExperimentSession
from lemonoids.agent import run_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(d: dict) -> str:
    return "  ".join(f"{k}: {v:.3f}" for k, v in d.items())


def _divider(title: str = "") -> None:
    if title:
        print(f"\n{'─' * 10} {title} {'─' * (40 - len(title))}")
    else:
        print()


# ---------------------------------------------------------------------------
# Walkthrough
# ---------------------------------------------------------------------------

def walkthrough() -> None:
    """Walk through the benchmark loop step by step — no API key needed."""

    # ------------------------------------------------------------------
    # 1. Generate a synthetic organism
    # ------------------------------------------------------------------
    _divider("1. Generate a synthetic organism")
    org = generate_organism(seed=42)
    obs_names = [g.name for g in org.genes if g.id in org.observable_genes]
    latent_count = len(org.genes) - len(org.observable_genes)
    print(f"Organism:  {org.id}")
    print(f"Genes:     {len(org.genes)} total  |  {len(obs_names)} observable  |  {latent_count} latent (hidden)")
    print(f"Modules:   {len(org.modules)}  (hidden from agent — inferring them is part of the challenge)")
    print(f"Signals:   {len(org.signals)}")
    print(f"Phenotypes:{len(org.phenotypes)}  — {', '.join(p.label for p in org.phenotypes)}")
    print(f"\nBaseline phenotypes (what the agent sees at t=0):")
    from lemonoids.dynamics import compute_phenotypes
    baseline = compute_phenotypes(org, org.baseline_state, noise=False)
    for label, val in baseline.items():
        print(f"  {label}: {val:.3f}")

    # ------------------------------------------------------------------
    # 2. Run a perturbation experiment
    # ------------------------------------------------------------------
    _divider("2. Run a perturbation experiment")
    session = ExperimentSession(org, seed=42)
    first_obs = obs_names[0]
    print(f"Intervention: BLOCK {first_obs}  (costs 1 budget unit)")
    result = session.run_experiment({first_obs: {"type": "BLOCK"}})
    print(f"Budget remaining: {result['budget_remaining']} / {session.budget}")
    print(f"Phenotype readout after BLOCK {first_obs}:")
    for label, val in result["phenotypes"].items():
        delta = val - baseline[label]
        arrow = f"({delta:+.3f})"
        print(f"  {label}: {val:.3f}  {arrow}")

    # ------------------------------------------------------------------
    # 3. Prediction task
    # ------------------------------------------------------------------
    _divider("3. Prediction task")
    print("Agent goal: predict phenotypes under a held-out intervention.")
    task = session.get_next_prediction_task()
    print(f"Task {task['task_id']}: what are the phenotypes if we apply — {task['interventions']}?")
    print("(Ground truth is hidden; agent must reason from experiments to predict.)")

    # Submit a naive guess (all 0.5) to show the scoring API
    naive_pred = {p.label: 0.5 for p in org.phenotypes}
    score = session.submit_prediction(task["task_id"], naive_pred)
    print(f"\nNaive prediction (all 0.5):  MSE={score['mse']:.4f}  accuracy={score['accuracy']:.0%}")
    print("Ground truth vs prediction:")
    for label, detail in score["details"].items():
        gt = detail["ground_truth"]
        pred = detail["prediction"]
        ok = "✓" if detail["within_threshold"] else "✗"
        print(f"  {label}: predicted {pred:.3f}  actual {gt:.3f}  {ok}")

    # ------------------------------------------------------------------
    # 4. Disease mode
    # ------------------------------------------------------------------
    _divider("4. Disease mode")
    disease_org = generate_disease_organism(seed=42)
    print(f"Cell type: {disease_org.cell_type.label}")
    print(f"Malfunction: {disease_org.malfunctions[0].description}")
    from lemonoids.dynamics import compute_phenotypes as cp
    disease_phenos = cp(disease_org, disease_org.baseline_state, noise=False)
    print(f"\nPhenotypes vs healthy ranges:")
    for p in disease_org.phenotypes:
        val = disease_phenos[p.label]
        lo, hi = disease_org.healthy_phenotype_ranges[p.label]
        status = "OK" if lo <= val <= hi else "ABERRANT"
        print(f"  {p.label}: {val:.3f}  (healthy {lo:.2f}–{hi:.2f})  [{status}]")

    disease_session = ExperimentSession(disease_org, budget=10, seed=42)
    disease_session.submit_malfunction_hypothesis(disease_org.malfunctions[0].target_name,
                                                  disease_org.malfunctions[0].type)
    rescue_gene = obs_names[1] if len(obs_names) > 1 else obs_names[0]
    rescue = disease_session.test_rescue({rescue_gene: {"type": "BLOCK"}})
    print(f"\nRescue attempt (BLOCK {rescue_gene}):")
    print(f"  Phenotypes restored: {rescue['restored_fraction']:.0%}")
    print(f"  MSE vs healthy:      {rescue['mse_vs_healthy']:.4f}")

    # ------------------------------------------------------------------
    # 5. Sanity checks (silent unless something breaks)
    # ------------------------------------------------------------------
    _divider("5. Sanity checks")
    org2 = type(org).from_json(org.to_json())
    assert org.id == org2.id, "JSON round-trip failed"

    import os
    from lemonoids import generate_dataset
    paths = generate_dataset(n_organisms=3, experiments_per_organism=2,
                             output_path="/tmp/lemonoids_test_dataset", seed=7)
    with open(paths["organisms"]) as f:
        orgs_data = json.load(f)
    with open(paths["experiments"]) as f:
        exps_data = json.load(f)
    assert len(orgs_data) == 3
    assert len(exps_data) == 6
    org_ids = {o["id"] for o in orgs_data}
    assert {e["organism_id"] for e in exps_data} <= org_ids
    print("JSON serialization:     OK")
    print("Dataset generation:     OK  (3 organisms × 2 experiments)")

    print("\n=== All checks passed ===\n")


# ---------------------------------------------------------------------------
# Agent demos
# ---------------------------------------------------------------------------

def agent_demo(model: str) -> None:
    import os
    os.makedirs("logs", exist_ok=True)
    log_path = "logs/demo_agent.json"
    print(f"\n=== Agent Demo ({model}) ===")
    org = generate_organism(n_genes=15, n_modules=3, seed=42)
    session = ExperimentSession(org, budget=15, seed=42)
    summary = run_agent(session, model=model, max_turns=40, verbose=True, log_path=log_path)
    print("\nFinal summary:")
    print(json.dumps(summary, indent=2))
    print(f"\nSession log:    {log_path}")
    print(f"HTML report:    {log_path.replace('.json', '.html')}")


def disease_agent_demo(model: str) -> None:
    import os
    os.makedirs("logs", exist_ok=True)
    log_path = "logs/demo_agent_disease.json"
    print(f"\n=== Disease Agent Demo ({model}) ===")
    org = generate_disease_organism(n_genes=15, n_modules=3, seed=42)
    session = ExperimentSession(org, budget=15, seed=42)
    summary = run_agent(session, model=model, max_turns=40, verbose=True, log_path=log_path)
    print("\nFinal summary:")
    print(json.dumps(summary, indent=2))
    print(f"\nSession log:    {log_path}")
    print(f"HTML report:    {log_path.replace('.json', '.html')}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    walkthrough()

    if "--agent" in sys.argv:
        # Pick model: --model <name> or default to gpt-4o
        model = "gpt-4o"
        if "--model" in sys.argv:
            idx = sys.argv.index("--model")
            if idx + 1 < len(sys.argv):
                model = sys.argv[idx + 1]

        if "--disease" in sys.argv:
            disease_agent_demo(model)
        else:
            agent_demo(model)
    else:
        print("Run with --agent to execute a full LLM agent session.")
        print("Run with --agent --disease for disease mode.")
        print("Use --model <name> to choose a model (default: gpt-4o).")
        print("Requires OPENAI_API_KEY or ANTHROPIC_API_KEY depending on model.")
