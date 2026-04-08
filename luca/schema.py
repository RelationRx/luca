"""Dataclass schema for LUCA organisms."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml


@dataclass
class CellType:
    id: str           # e.g. "ct_03"
    label: str        # e.g. "secretory-cell-Q"
    description: str  # human-readable cell type description


@dataclass
class Malfunction:
    type: str         # "LOCK_HI" | "LOCK_LO" | "PERSIST"
    target: str       # gene_id or signal_id
    target_name: str  # gene name or signal label (for readability)
    severity: float   # magnitude of perturbation applied
    description: str  # e.g. "Constitutive activation of G007"


@dataclass
class Gene:
    id: str    # e.g. "g_001"
    name: str  # e.g. "G001"


@dataclass
class Module:
    id: str          # e.g. "m_03"
    label: str       # e.g. "ion-flux-regulator"
    gene_ids: list[str]


@dataclass
class Signal:
    id: str           # e.g. "s_02"
    label: str        # e.g. "nutrient-X"
    targets: list[str]  # list of gene_ids
    mode: str         # "activates" or "inhibits"
    strength: float   # how much is added to z_i (signed per mode)


@dataclass
class Relation:
    src: str      # gene_id
    dst: str      # gene_id
    type: str     # "activates" or "inhibits"
    strength: float


@dataclass
class PhenotypeReadout:
    type: str             # "sigmoid_weighted_sum"
    depends_on: list[str] # gene_ids
    weights: list[float]
    bias: float


@dataclass
class Phenotype:
    id: str        # e.g. "p_growth"
    label: str     # e.g. "growth-rate"
    readout: PhenotypeReadout


@dataclass
class DynamicsConfig:
    type: str = "continuous_sigmoid"
    dt: float = 1.0
    noise_sigma: float = 0.01
    sigmoid_steepness: float = 1.0   # controls non-linearity; <1 = near-linear, >1 = sharper
    convergence_tol: float = 1e-3    # fixed-point convergence threshold
    rule: dict[str, Any] = field(default_factory=dict)
    # rule[gene_id] = {"bias": float, "inputs": [{"src": gene_id, "weight": float}]}


@dataclass
class Organism:
    id: str
    genes: list[Gene]
    modules: list[Module]
    signals: list[Signal]
    relations: list[Relation]
    phenotypes: list[Phenotype]
    dynamics: DynamicsConfig
    seed: int
    baseline_state: dict[str, float] = field(default_factory=dict)
    observable_genes: list[str] = field(default_factory=list)
    # Disease extension fields (None/empty for healthy organisms)
    cell_type: CellType | None = None
    healthy_baseline: dict[str, float] = field(default_factory=dict)
    healthy_phenotype_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    malfunctions: list[Malfunction] = field(default_factory=list)
    # Difficulty extension
    difficulty: str = "medium"
    latent_genes: list[str] = field(default_factory=list)  # hidden/untargetable genes
    # Diagnosis ambiguity: number of other effective (gene/signal, type) pairs whose
    # disease phenotype signature is within 0.1 max-abs-diff of the true malfunction.
    # 0 = uniquely identifiable from phenotype signature alone.
    # >0 = ambiguous; perturbation experiments needed to discriminate.
    n_diagnosis_alternatives: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert tuple ranges to lists for JSON compatibility (asdict already does this,
        # but be explicit so from_dict can reconstruct tuples)
        if d.get("healthy_phenotype_ranges"):
            d["healthy_phenotype_ranges"] = {
                k: list(v) for k, v in d["healthy_phenotype_ranges"].items()
            }
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Organism":
        genes = [Gene(**g) for g in d["genes"]]
        modules = [Module(**m) for m in d["modules"]]
        signals = [Signal(**s) for s in d["signals"]]
        relations = [Relation(**r) for r in d["relations"]]
        phenotypes = [
            Phenotype(
                id=p["id"],
                label=p["label"],
                readout=PhenotypeReadout(**p["readout"]),
            )
            for p in d["phenotypes"]
        ]
        dynamics = DynamicsConfig(**d["dynamics"])

        # Disease extension fields
        ct_data = d.get("cell_type")
        cell_type = CellType(**ct_data) if ct_data else None

        malfunctions = [Malfunction(**m) for m in d.get("malfunctions", [])]

        # Ranges stored as lists in JSON — convert back to tuples
        raw_ranges = d.get("healthy_phenotype_ranges", {})
        healthy_phenotype_ranges = {k: tuple(v) for k, v in raw_ranges.items()}  # type: ignore[misc]

        return cls(
            id=d["id"],
            genes=genes,
            modules=modules,
            signals=signals,
            relations=relations,
            phenotypes=phenotypes,
            dynamics=dynamics,
            seed=d["seed"],
            baseline_state=d.get("baseline_state", {}),
            observable_genes=d.get("observable_genes", []),
            cell_type=cell_type,
            healthy_baseline=d.get("healthy_baseline", {}),
            healthy_phenotype_ranges=healthy_phenotype_ranges,
            malfunctions=malfunctions,
            difficulty=d.get("difficulty", "medium"),
            latent_genes=d.get("latent_genes", []),
            n_diagnosis_alternatives=d.get("n_diagnosis_alternatives", 0),
        )

    @classmethod
    def from_json(cls, s: str) -> "Organism":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_yaml(cls, s: str) -> "Organism":
        return cls.from_dict(yaml.safe_load(s))
