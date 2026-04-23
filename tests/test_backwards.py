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
