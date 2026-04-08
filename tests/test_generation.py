"""Tests for organism generation."""
import pytest
from luca import generate_organism, generate_disease_organism
from luca.dynamics import compute_phenotypes


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


def test_generate_organism_n_genes_minimum():
    """n_genes < 2 should raise a clear ValueError."""
    with pytest.raises(ValueError, match="n_genes"):
        generate_organism(n_genes=1, seed=0)


def test_generate_organism_n_modules_minimum():
    """n_modules < 1 should raise a clear ValueError."""
    with pytest.raises(ValueError, match="n_modules"):
        generate_organism(n_modules=0, seed=0)


def test_canonical_benchmark_stability():
    """Seeds 0–4 on medium difficulty must produce stable organisms across runs."""
    for seed in range(5):
        org_a = generate_organism(seed=seed, n_genes=15, n_modules=4)
        org_b = generate_organism(seed=seed, n_genes=15, n_modules=4)
        assert org_a.id == org_b.id, f"seed={seed}: organism id changed"
        assert org_a.baseline_state == org_b.baseline_state, f"seed={seed}: baseline_state changed"
        assert len(org_a.genes) == len(org_b.genes), f"seed={seed}: gene count changed"


def test_diagnosis_ambiguity_is_non_negative():
    """n_diagnosis_alternatives must always be >= 0 and present on disease organisms."""
    for seed in range(5):
        org = generate_disease_organism(seed=seed)
        assert hasattr(org, "n_diagnosis_alternatives")
        assert org.n_diagnosis_alternatives >= 0


def test_diagnosis_ambiguity_serializes():
    """n_diagnosis_alternatives must survive JSON round-trip."""
    org = generate_disease_organism(seed=2)
    org2 = type(org).from_json(org.to_json())
    assert org2.n_diagnosis_alternatives == org.n_diagnosis_alternatives


def test_disease_detectability_guarantee():
    """Every disease organism must have ≥1 aberrant phenotype AND a rescuable malfunction."""
    from luca.dynamics import compute_phenotypes, simulate_sigmoid
    import numpy as np

    for seed in range(5):
        org = generate_disease_organism(seed=seed)

        # Condition 1: at least one phenotype is outside its healthy range
        disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
        aberrant = [
            lbl for lbl, val in disease_phenos.items()
            if not (org.healthy_phenotype_ranges[lbl][0] <= val <= org.healthy_phenotype_ranges[lbl][1])
        ]
        assert aberrant, f"seed={seed}: no aberrant phenotypes found"

        # Condition 2: the documented corrective intervention restores ≥1 aberrant phenotype
        restored = False
        for m in org.malfunctions:
            if m.type == "LOCK_HI":
                iv = {m.target: {"type": "BLOCK"}}
                r = simulate_sigmoid(org, interventions=iv, active_signals={},
                                     rng=np.random.default_rng(0))
            elif m.type == "LOCK_LO":
                iv = {m.target: {"type": "BOOST"}}
                r = simulate_sigmoid(org, interventions=iv, active_signals={},
                                     rng=np.random.default_rng(0))
            else:  # PERSIST — removing the override = no active signals
                r = simulate_sigmoid(org, interventions={}, active_signals={},
                                     rng=np.random.default_rng(0))
            rescue_phenos = compute_phenotypes(org, r["final_state"], noise=False)
            if any(
                org.healthy_phenotype_ranges[lbl][0] <= rescue_phenos.get(lbl, 0.5) <= org.healthy_phenotype_ranges[lbl][1]
                for lbl in aberrant
            ):
                restored = True
                break
        assert restored, f"seed={seed}: no corrective intervention restores any aberrant phenotype"
