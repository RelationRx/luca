"""Tests for backwards-organism generation (luca/backwards.py)."""
import pytest

from luca import generate_organism, generate_disease_organism
from luca.backwards import invert_organism
from luca.dynamics import compute_phenotypes


# --- scaffold test ------------------------------------------------------

def test_invert_organism_returns_organism():
    org = generate_organism(seed=0)
    inverted = invert_organism(org)
    assert type(inverted).__name__ == "Organism"
    assert inverted is not org  # pure function returns a new object


# --- sign-flip surface tests --------------------------------------------

def _count_positive_negative(values):
    pos = sum(1 for v in values if v > 0)
    neg = sum(1 for v in values if v < 0)
    return pos, neg


def test_edge_weight_signs_swap():
    org = generate_organism(seed=0)
    forward_weights = [
        inp["weight"]
        for dst, r in org.dynamics.rule.items()
        for inp in r.get("inputs", [])
    ]
    forward_pos, forward_neg = _count_positive_negative(forward_weights)

    inverted = invert_organism(org)
    backward_weights = [
        inp["weight"]
        for dst, r in inverted.dynamics.rule.items()
        for inp in r.get("inputs", [])
    ]
    backward_pos, backward_neg = _count_positive_negative(backward_weights)

    assert forward_pos == backward_neg
    assert forward_neg == backward_pos


def test_relation_types_swap():
    org = generate_organism(seed=0)
    forward_activates = sum(1 for r in org.relations if r.type == "activates")
    forward_inhibits = sum(1 for r in org.relations if r.type == "inhibits")

    inverted = invert_organism(org)
    backward_activates = sum(1 for r in inverted.relations if r.type == "activates")
    backward_inhibits = sum(1 for r in inverted.relations if r.type == "inhibits")

    assert forward_activates == backward_inhibits
    assert forward_inhibits == backward_activates


def test_signal_modes_swap():
    org = generate_organism(seed=0)
    forward_modes = [s.mode for s in org.signals]
    inverted = invert_organism(org)
    backward_modes = [s.mode for s in inverted.signals]
    for fm, bm in zip(forward_modes, backward_modes):
        assert (fm == "activates" and bm == "inhibits") or (fm == "inhibits" and bm == "activates")


def test_phenotype_weight_signs_swap():
    org = generate_organism(seed=0)
    forward_weights = [w for ph in org.phenotypes for w in ph.readout.weights]
    forward_pos, forward_neg = _count_positive_negative(forward_weights)

    inverted = invert_organism(org)
    backward_weights = [w for ph in inverted.phenotypes for w in ph.readout.weights]
    backward_pos, backward_neg = _count_positive_negative(backward_weights)

    assert forward_pos == backward_neg
    assert forward_neg == backward_pos


def test_bias_signs_flip():
    org = generate_organism(seed=0)
    forward_biases = [org.dynamics.rule[g.id]["bias"] for g in org.genes]

    inverted = invert_organism(org)
    backward_biases = [inverted.dynamics.rule[g.id]["bias"] for g in inverted.genes]

    for fb, bb in zip(forward_biases, backward_biases):
        assert fb == pytest.approx(-bb, abs=1e-12)


def test_backwards_baseline_phenotypes_centered():
    """Construction guarantee 4: baseline phenotypes stay near 0.5."""
    for seed in [0, 1, 7, 13]:
        org = generate_organism(seed=seed)
        inverted = invert_organism(org)
        phenos = compute_phenotypes(inverted, inverted.baseline_state, noise=False)
        for label, val in phenos.items():
            assert 0.3 <= val <= 0.7, (
                f"seed={seed}: backwards phenotype {label}={val:.3f} outside [0.3, 0.7]"
            )


def test_backwards_baseline_differs_from_forward():
    """Sanity: backwards dynamics actually produce different fixed points."""
    org = generate_organism(seed=0)
    inverted = invert_organism(org)
    forward_state = org.baseline_state
    backward_state = inverted.baseline_state

    # At least one gene should differ by > 0.05 (noise floor); otherwise
    # inversion is a no-op and the ablation has no signal.
    max_diff = max(
        abs(forward_state.get(gid, 0.5) - backward_state.get(gid, 0.5))
        for gid in forward_state.keys()
    )
    assert max_diff > 0.05, (
        f"Backwards baseline max gene delta {max_diff:.3f} — inversion has no effect"
    )


# --- latent-detectability repair (hard tier) ----------------------------
#
# Medium tier (the ablation's scope) has latent_fraction=0, so the repair
# is a no-op there. Hard tier has latent genes but backwards dynamics may
# not converge (dense feedback → mutual inhibition after inversion). We
# verify the helper runs without crashing and the latent-gene list is
# preserved — not that every latent gene is still detectable under the
# 0.05 threshold, which is not guaranteed under non-convergent dynamics.

def test_backwards_hard_tier_preserves_latent_genes():
    for seed in [0, 1, 2, 3, 4]:
        org = generate_organism(seed=seed, difficulty="hard")
        inverted = invert_organism(org)
        assert inverted.latent_genes == org.latent_genes, (
            f"seed={seed}: latent gene list changed across inversion"
        )


def test_backwards_medium_tier_repair_is_noop():
    """Medium tier has no latent genes; repair must not add phenotype terms."""
    org = generate_organism(seed=0, difficulty="medium")
    forward_depends = [list(ph.readout.depends_on) for ph in org.phenotypes]
    inverted = invert_organism(org)
    backward_depends = [list(ph.readout.depends_on) for ph in inverted.phenotypes]
    assert forward_depends == backward_depends, (
        "Medium-tier inversion should not add any phenotype readout contributors"
    )


# --- disease-organism guard ---------------------------------------------

def test_invert_organism_rejects_disease_organism():
    disease_org = generate_disease_organism(seed=7)
    with pytest.raises(ValueError, match="healthy organisms only"):
        invert_organism(disease_org)


# --- generate_organism(backwards=True) integration ----------------------

def test_generate_organism_backwards_matches_post_hoc_invert():
    """generate_organism(backwards=True) must equal invert_organism(generate_organism())."""
    direct = generate_organism(seed=0, backwards=True)
    post_hoc = invert_organism(generate_organism(seed=0))

    assert direct.dynamics.rule == post_hoc.dynamics.rule
    for d_ph, p_ph in zip(direct.phenotypes, post_hoc.phenotypes):
        assert d_ph.readout.weights == p_ph.readout.weights
        assert d_ph.readout.bias == pytest.approx(p_ph.readout.bias, abs=1e-9)


def test_generate_organism_backwards_is_reproducible():
    a = generate_organism(seed=42, backwards=True)
    b = generate_organism(seed=42, backwards=True)
    assert a.baseline_state == b.baseline_state
    assert a.dynamics.rule == b.dynamics.rule


def test_generate_organism_backwards_differs_from_forward():
    forward = generate_organism(seed=42)
    backward = generate_organism(seed=42, backwards=True)
    assert len(forward.relations) == len(backward.relations)
    fwd_activates = sum(1 for r in forward.relations if r.type == "activates")
    bwd_activates = sum(1 for r in backward.relations if r.type == "activates")
    fwd_inhibits = len(forward.relations) - fwd_activates
    bwd_inhibits = len(backward.relations) - bwd_activates
    assert fwd_activates == bwd_inhibits
    assert fwd_inhibits == bwd_activates


# --- generate_disease_organism(backwards=True) --------------------------

def test_generate_disease_organism_backwards_valid():
    """Backwards disease organism must still satisfy detectability guarantee."""
    org = generate_disease_organism(seed=7, backwards=True)
    assert len(org.malfunctions) >= 1
    assert org.cell_type is not None
    assert org.healthy_baseline != {}

    disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    aberrant = [
        lbl for lbl, v in disease_phenos.items()
        if not (
            org.healthy_phenotype_ranges[lbl][0]
            <= v
            <= org.healthy_phenotype_ranges[lbl][1]
        )
    ]
    assert len(aberrant) >= 1


def test_generate_disease_organism_backwards_rescuable():
    """Backwards disease organism must have a corrective single intervention."""
    from luca.dynamics import simulate_sigmoid
    import numpy as np

    org = generate_disease_organism(seed=7, backwards=True)
    m = org.malfunctions[0]

    if m.type == "LOCK_HI":
        corrective = {m.target: {"type": "BLOCK"}}
        active_signals = {}
    elif m.type == "LOCK_LO":
        corrective = {m.target: {"type": "BOOST"}}
        active_signals = {}
    else:  # PERSIST — deactivate the signal override
        corrective = {}
        active_signals = {}

    rescue = simulate_sigmoid(
        org,
        interventions=corrective,
        active_signals=active_signals,
        rng=np.random.default_rng(7 + 5678),
    )
    rescue_phenos = compute_phenotypes(org, rescue["final_state"], noise=False)
    disease_phenos = compute_phenotypes(org, org.baseline_state, noise=False)
    aberrant = [
        lbl for lbl, v in disease_phenos.items()
        if not (
            org.healthy_phenotype_ranges[lbl][0]
            <= v
            <= org.healthy_phenotype_ranges[lbl][1]
        )
    ]
    rescued = any(
        org.healthy_phenotype_ranges[lbl][0]
        <= rescue_phenos.get(lbl, 0.5)
        <= org.healthy_phenotype_ranges[lbl][1]
        for lbl in aberrant
    )
    assert rescued, (
        f"No aberrant phenotype was rescued by corrective intervention for {m}"
    )
