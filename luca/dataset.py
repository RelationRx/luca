"""Offline dataset generation for LUCA benchmarking."""
from __future__ import annotations

import json
import os
import random
from typing import Any

import numpy as np

from .dynamics import simulate_sigmoid
from .generation import generate_organism
from .schema import Organism


def generate_dataset(
    n_organisms: int = 10,
    experiments_per_organism: int = 5,
    complexity_range: dict[str, tuple[int, int]] | None = None,
    output_path: str = "luca_dataset",
    seed: int = 42,
) -> dict[str, str]:
    """
    Generate a dataset of organisms with perturbation experiments.

    complexity_range: e.g. {"n_genes": (10, 30), "n_modules": (3, 6)}
    Writes:
      {output_path}/organisms.json    — ground truth organisms
      {output_path}/experiments.json  — intervention/phenotype logs
    Returns dict with paths.
    """
    if complexity_range is None:
        complexity_range = {"n_genes": (10, 20), "n_modules": (3, 5)}

    rng_py = random.Random(seed)
    os.makedirs(output_path, exist_ok=True)

    organisms_data: list[dict] = []
    experiments_data: list[dict] = []

    for i in range(n_organisms):
        org_seed = rng_py.randint(0, 2**31 - 1)

        # Sample complexity
        n_genes = rng_py.randint(*complexity_range.get("n_genes", (10, 20)))
        n_modules = rng_py.randint(*complexity_range.get("n_modules", (3, 5)))
        n_signals = rng_py.randint(2, 4)
        n_phenotypes = rng_py.randint(2, 4)

        org = generate_organism(
            n_genes=n_genes,
            n_modules=n_modules,
            n_signals=n_signals,
            n_phenotypes=n_phenotypes,
            seed=org_seed,
        )

        organisms_data.append(org.to_dict())

        # Generate experiments
        gene_ids = [g.id for g in org.genes]
        iv_types = ["BLOCK", "BOOST", "DAMPEN"]
        exp_rng = np.random.default_rng(org_seed)
        exp_rng_py = random.Random(org_seed)

        org_experiments: list[dict] = []
        for j in range(experiments_per_organism):
            n_iv = exp_rng_py.randint(1, 2)
            target_genes = exp_rng_py.sample(gene_ids, min(n_iv, len(gene_ids)))
            interventions = {
                gid: {"type": exp_rng_py.choice(iv_types)}
                for gid in target_genes
            }
            result = simulate_sigmoid(
                org,
                interventions=interventions,
                active_signals={},
                rng=exp_rng,
            )
            # Use gene names for readability
            id_to_name = {g.id: g.name for g in org.genes}
            named_interventions = {
                id_to_name.get(gid, gid): iv
                for gid, iv in interventions.items()
            }
            org_experiments.append({
                "organism_id": org.id,
                "experiment_id": f"{org.id}_exp_{j:02d}",
                "interventions": named_interventions,
                "result": {
                    "phenotypes": result["phenotypes"],
                    "status": result["status"],
                    "steps": result["steps"],
                },
            })

        experiments_data.extend(org_experiments)

    organisms_path = os.path.join(output_path, "organisms.json")
    experiments_path = os.path.join(output_path, "experiments.json")

    with open(organisms_path, "w") as f:
        json.dump(organisms_data, f, indent=2)

    with open(experiments_path, "w") as f:
        json.dump(experiments_data, f, indent=2)

    print(f"[dataset] Wrote {n_organisms} organisms → {organisms_path}")
    print(f"[dataset] Wrote {len(experiments_data)} experiments → {experiments_path}")

    return {"organisms": organisms_path, "experiments": experiments_path}
