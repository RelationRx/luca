"""Pydantic-style dataclasses for BioWorld organisms."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml


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

    def to_dict(self) -> dict:
        return asdict(self)

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
        )

    @classmethod
    def from_json(cls, s: str) -> "Organism":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_yaml(cls, s: str) -> "Organism":
        return cls.from_dict(yaml.safe_load(s))
