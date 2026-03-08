# Contributing to LEMONOIDS

## Setup

```bash
git clone <repo-url>
cd lemonoids
pip install -e ".[dev]"
```

## Project structure

```
lemonoids/          # Core package
demo.py             # Smoke tests + agent demo
inspect_organism.py # CLI inspector
experiments/        # (local only, not tracked) experiment scripts and results
logs/               # (local only, not tracked) agent session logs
```

## Running smoke tests

```bash
python demo.py
```

## Code style

- Python 3.10+, type hints where practical
- Line length 100 (`ruff check .`)
- No external biological vocabulary in agent-facing strings — all gene names, signals, and malfunction types must be abstract (see Design Principles in README)

## Key design invariants to preserve

1. **Vocabulary isolation** — intervention types (`BLOCK`/`BOOST`/`DAMPEN`), malfunction types (`LOCK_HI`/`LOCK_LO`/`PERSIST`), and all organism labels must remain free of real biological terminology so agents cannot exploit pretraining priors.

2. **Rescue oracle protection** — `test_rescue()` requires `submit_malfunction_hypothesis()` to be called first. The hypothesis is locked on first submission and the score is withheld until `get_summary()`. Do not remove these guards.

3. **Detectability guarantee** — `generate_disease_organism()` guarantees that every returned organism has (a) at least one aberrant phenotype and (b) a corrective intervention that restores it. Any changes to generation must preserve this.

4. **Latent genes** — Malfunction target genes must never be latent (agent needs to be able to target them). This invariant is enforced at the end of `generate_disease_organism()`.

## Adding a new experiment

Create a self-contained subdirectory under `experiments/`:
```
experiments/my_experiment/
├── run.py       # generates results_*.jsonl
└── fig.py       # reads results and produces figures
```

`experiments/` is gitignored — share results and figures separately.

## Questions

Open an issue or reach out to the maintainers.
