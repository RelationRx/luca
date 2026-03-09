"""Tests for organism generation."""
import pytest
from lemonoids import generate_organism, generate_disease_organism
from lemonoids.dynamics import compute_phenotypes


def test_generate_organism_defaults():
    org = generate_organism(seed=0)
    assert len(org.genes) == 20
    assert len(org.modules) == 4
    assert len(org.phenotypes) >= 1
    assert len(org.signals) >= 1
    assert org.baseline_state != {}


def test_generate_organism_custom_size():
    org = generate_organism(n_genes=10, n_modules=3, seed=1)
    assert len(org.genes) == 10
    assert len(org.modules) == 3


def test_generate_organism_reproducible():
    org_a = generate_organism(seed=42)
    org_b = generate_organism(seed=42)
    assert org_a.id == org_b.id
    assert org_a.baseline_state == org_b.baseline_state


def test_generate_organism_different_seeds():
    org_a = generate_organism(seed=1)
    org_b = generate_organism(seed=2)
    assert org_a.id != org_b.id


def test_observable_genes_subset():
    org = generate_organism(seed=0)
    gene_ids = {g.id for g in org.genes}
    assert set(org.observable_genes) <= gene_ids


def test_json_round_trip():
    org = generate_organism(seed=5)
    org2 = type(org).from_json(org.to_json())
    assert org.id == org2.id
    assert org.baseline_state == org2.baseline_state
    assert len(org2.genes) == len(org.genes)


def test_yaml_round_trip():
    org = generate_organism(seed=5)
    org2 = type(org).from_yaml(org.to_yaml())
    assert org.id == org2.id


def test_disease_organism_has_malfunction():
    org = generate_disease_organism(seed=7)
    assert org.cell_type is not None
    assert len(org.malfunctions) >= 1
    assert org.healthy_baseline != {}
    assert org.healthy_phenotype_ranges != {}


def test_disease_organism_has_aberrant_phenotypes():
    org = generate_disease_organism(seed=7)
    disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    aberrant = [
        label for label, val in disease_phenos.items()
        if not (org.healthy_phenotype_ranges[label][0] <= val <= org.healthy_phenotype_ranges[label][1])
    ]
    assert len(aberrant) >= 1, "Disease organism should have at least one aberrant phenotype"


def test_disease_json_round_trip():
    org = generate_disease_organism(seed=7)
    org2 = type(org).from_json(org.to_json())
    assert org2.cell_type is not None
    assert org2.cell_type.label == org.cell_type.label
    assert len(org2.malfunctions) == len(org.malfunctions)
    assert org2.healthy_phenotype_ranges != {}


def test_malfunction_target_not_latent():
    """Malfunction targets must always be observable (not latent)."""
    for seed in range(5):
        org = generate_disease_organism(seed=seed)
        latent = set(org.latent_genes)
        for m in org.malfunctions:
            assert m.target not in latent, (
                f"Malfunction target {m.target} is latent in seed={seed}"
            )
