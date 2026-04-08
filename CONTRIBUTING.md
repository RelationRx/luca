# Contributing to LUCA

We welcome contributions — the easiest way to help is to **use the benchmark** and share what you find.

## Ways to contribute

Browse [open issues](../../issues) for specific tasks. Most are self-contained and optional:

- **Getting started** — run the benchmark, try the BYOA interface, report any friction
- **Add a model** — run your favourite LLM (Gemini, Qwen, Llama, etc.) and share session logs
- **Add a baseline** — implement a non-LLM baseline (linear regression, kNN, random forest)
- **Analysis** — post-hoc analyses computable from existing session logs (no re-runs needed)

No contribution is too small. Even a bug report or a note about unclear docs is useful.

## Setup

```bash
git clone <repo-url>
cd luca
pip install -e ".[dev]"
```

## Project structure

```
luca/          # Core package
tests/              # pytest suite (run with: python -m pytest tests/)
demo.py             # Smoke tests + agent demo
inspect_organism.py # CLI inspector
evaluate.py         # Benchmark evaluation script
experiments/        # Experiment scripts (tracked) + summary results
results/            # (local only, not tracked) evaluation output
logs/               # (local only, not tracked) agent session logs
```

## Running tests

```bash
python -m pytest tests/ -v
```

## Running smoke tests

```bash
python demo.py
```

## Running the benchmark

```bash
python evaluate.py --heuristic --n 5        # no API key required
python evaluate.py --model claude-opus-4-6  # requires ANTHROPIC_API_KEY
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

Experiment scripts and summary `.jsonl` files are tracked. Per-session logs (`logs/`) and figures (`*.png`) are gitignored.

## Submitting results

If you run a new model or baseline, the most useful thing to submit is:
1. Session logs (JSONL files from `experiments/`)
2. Model identifier and provider
3. Any notes on integration (did tool calling work? any quirks?)

Open a PR or attach logs to the relevant issue.

## Questions

Open an issue or reach out to the maintainers.
