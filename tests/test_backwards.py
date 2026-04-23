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
