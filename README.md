# 🍋 LEMONOIDS

**Synthetic organism reasoning benchmark for LLM agents**
![Example organism — seed 42](assets/org42.png)
A Python package that procedurally generates synthetic biological organisms (based on synthetic regulatory networks) and exposes them as a reasoning benchmark for LLM agents.

The world is **unknowable via retrieval** — gene names, module labels, signals, and pathways are all invented. Prior biological knowledge is useless. An agent must reason causally from perturbation experiments to succeed.

---

## 🧬 Design Principles

1. **Made-up vocabulary** — gene IDs e.g `G001`, modules labeled `"charge-flow-regulator"`, signals e.g`"substrate-X"`. No real gene or pathway names. Distinguishes causal reasoning from retrieval.
2. **Organism dynamics and complexity** — gene states follow `x_i(t+1) = σ(bias_i + Σ W_ij·x_j + signal_terms + ε)`, values in [0, 1] ([Mjolsness, Sharp & Reinitz, 1991](https://doi.org/10.1016/S0022-5193(05)80391-1); [Karlebach & Shamir, 2008](https://doi.org/10.1038/nrm2503)). Complexity is controlled along four axes:

   | Tier | Alias | Observability | FFL density | Feedback density | Latent genes | Noise |
   |------|-------|:---:|:---:|:---:|:---:|:---:|
   | `easy` | `prokaryote` | 80 % | 7 % | 0 % | 0 % | 0.005 |
   | `medium` | `simple_eukaryote` | 60 % | 13 % | 13 % | 0 % | 0.01 |
   | `hard` | `complex_eukaryote` | 50 % | 20 % | 27 % | 25 % | 0.03 |

   **`medium` is the default** and defines the canonical benchmark split (seeds 0–19). FFL and feedback densities are fractions of `n_genes`, so complexity scales with organism size. Latent genes = hidden confounders never visible or targetable.

3. **Named phenotype readouts** — non-linear summaries of an organism state e.g `"expansion-rate"` depending on gene states. The agent sees readout names and values, not raw gene states.
4. **JSON/YAML serialization** — organisms are fully serializable for reproducibility and offline evaluation.
5. **Disease mode** — organisms can be given a malfunction (LOCK_HI/LOCK_LO/PERSIST) that shifts phenotypes away from healthy ranges. Agents must diagnose and rescue.

---

## 🎯 The Task

LEMONOIDS is a benchmark for causal reasoning under a fixed experimental budget. Each session presents an agent with a freshly generated organism it has never seen — no prior knowledge applies. The agent must design perturbation experiments, build a causal model from the results, and make accurate predictions.

**The agent is given:**
- A set of observable genes and their baseline states
- Named phenotype readouts (not raw gene states)
- A budget of perturbation experiments

**The agent must:**
1. **Explore** — run experiments: BLOCK, BOOST, or DAMPEN genes, or activate signals. Each costs 1 budget unit.

   | Intervention | Effect |
   |---|---|
   | `BLOCK` | Suppress gene to 0.0 |
   | `BOOST` | Saturate gene to 1.0 |
   | `DAMPEN` | Clamp gene to ≤ 0.15 |
   | signal `"activate"` | Amplify signal input to targets |

2. **Predict** — submit phenotype values for 2 held-out intervention combinations not directly measured.
3. **Hypothesise** — submit a free-text causal summary of the network.
4. **Diagnose** *(disease mode)* — identify the malfunctioning gene or signal and its type.
5. **Rescue** *(disease mode)* — test an intervention that restores phenotypes to healthy ranges.

**Scoring:**

| Component | Metric | Mode |
|-----------|--------|------|
| Prediction accuracy | MSE + fraction within ±0.15 threshold | Both |
| Causal hypothesis | Stored free text — qualitative review | Both |
| Diagnosis | 1.0 exact · 0.5 right target wrong type · 0.0 wrong | Disease |
| Rescue | Fraction of aberrant phenotypes restored to healthy range | Disease |

> Prediction tasks are revealed one at a time — the next task only unlocks after the current one is submitted, preventing direct-measurement gaming. **Random baseline:** prediction MSE ≈ 0.08.

> Modules are **hidden from the agent** — inferring functional groupings is part of the challenge.

---

## ⚡ Quick Start

```bash
pip install -r requirements.txt

# Smoke test
python -c "from lemonoids import generate_organism; o = generate_organism(seed=0); print(o.id)"
```

### demo.py — walkthrough & agent demo

```bash
python demo.py                          # narrative walkthrough (no API key needed)
python demo.py --agent                  # run an agent session; saves logs/demo_agent.{json,html}
python demo.py --agent --model gpt-4.1  # choose model
python demo.py --agent --disease        # disease mode
```

| Flag | Default | Description |
|------|---------|-------------|
| `--agent` | off | Run an LLM agent session after the walkthrough |
| `--model MODEL` | `gpt-4o` | Model to use (e.g. `gpt-4.1`, `claude-opus-4-6`) |
| `--disease` | off | Use a disease organism |

### evaluate.py — benchmark evaluation

Runs the canonical benchmark: seeds 0–19, medium difficulty. Produces aggregate scores (MSE, accuracy, composite) across organisms.

```bash
python evaluate.py --heuristic                              # no API key required
python evaluate.py --model claude-opus-4-6                  # requires ANTHROPIC_API_KEY
python evaluate.py --model gpt-5.1                          # requires OPENAI_API_KEY
python evaluate.py --model claude-opus-4-6 --model gpt-5.1  # compare models
python evaluate.py --model claude-opus-4-6 --disease
python evaluate.py --model claude-opus-4-6 --difficulty hard
```

| Flag | Default | Description |
|------|---------|-------------|
| `--model MODEL` | — | Model to evaluate (repeatable for comparison) |
| `--heuristic` | off | Include the heuristic baseline (BLOCK each gene, predict additively) |
| `--disease` | off | Evaluate in disease mode |
| `--difficulty TIER` | `medium` | `easy` / `medium` / `hard` |
| `--n INT` | 20 | Number of organisms (uses canonical seeds 0…N-1) |
| `--seeds` | — | Override seeds: integers or range, e.g. `0 1 2` or `0:10` |
| `--out DIR` | `results/` | Output directory for JSONL results and logs |

---

## 🔍 Inspector CLI

Visualise and explore individual organisms. Use `evaluate.py` for multi-seed benchmarking; use `--replay` here to run a single agent session and inspect its reasoning in detail.

```bash
# Terminal summary + interactive graph (default: seed=42, medium difficulty)
python inspect_organism.py
python inspect_organism.py --seed 7 --difficulty hard

# Figure only / terminal only
python inspect_organism.py --seed 7 --save org.png --no-show
python inspect_organism.py --no-plot

# Disease organism: terminal comparison + optional side-by-side GRN figure
python inspect_organism.py --disease --seed 7 --no-plot
python inspect_organism.py --disease --compare --seed 7 --no-show --save disease.png

# Single-organism agent session — saves JSON + HTML trace for inspection
# (for multi-seed evaluation use evaluate.py)
python inspect_organism.py --replay --seed 42 --log logs/run.json
python inspect_organism.py --replay --disease --model gpt-4o --seed 42 --log logs/run.json --trace
```

| Flag | Default | Description |
|------|---------|-------------|
| `--seed INT` | 42 | Organism seed |
| `--difficulty TIER` | `medium` | `easy` / `medium` / `hard` |
| `--disease` | off | Disease organism (terminal: healthy vs disease comparison) |
| `--compare` | off | Side-by-side healthy vs disease GRN figure (with `--disease`) |
| `--replay` | off | Run a single agent session for inspection; save JSON + HTML with `--log` |
| `--model MODEL` | `claude-opus-4-6` | Model for `--replay` |
| `--log PATH` | — | Save agent session log to JSON and generate HTML report |
| `--trace` | off | Print turn-by-turn trace after replay |
| `--save PATH` | — | Save figure to file |
| `--no-show` | off | Skip interactive plot window |
| `--no-plot` | off | Skip figure entirely |

**Programmatic usage:**
```python
from lemonoids import generate_organism
from lemonoids.inspect import print_organism, plot_organism

org = generate_organism(seed=42)
print_organism(org)                          # terminal
plot_organism(org, save_path="org.png")      # figure
```

---

## 📁 Package Structure

```
lemonoids/
├── __init__.py       # Public API
├── schema.py         # Dataclasses: Gene, Module, Signal, Relation, Phenotype,
│                     #   DynamicsConfig, Organism, CellType, Malfunction
├── vocabulary.py     # Word banks for invented abstract names + cell types
├── generation.py     # generate_organism(), generate_disease_organism()
├── dynamics.py       # simulate_sigmoid(), compute_phenotypes()
├── experiment.py     # ExperimentSession — budget, interventions, scoring
├── dataset.py        # generate_dataset() — JSON export for offline benchmarking
├── agent.py          # Tool definitions + run_agent() (Anthropic + OpenAI)
├── inspect.py        # plot_organism(), plot_disease_organism(), plot_session()
└── report.py         # print_session_trace(), export_session_html()

evaluate.py           # Benchmark evaluation script
demo.py               # Smoke tests + agent demo entry point
inspect_organism.py   # CLI inspector and replay tool
tests/                # pytest suite
requirements.txt
```

---

## 📖 API Reference

Full API documentation — `generate_organism()`, `generate_disease_organism()`, `ExperimentSession`, `run_agent()`, diagnostic reports, `generate_dataset()` — is in **[docs/api.md](docs/api.md)**.

---

## 📦 Dependencies

```
anthropic>=0.40.0    # Anthropic Claude API (agent loop)
openai>=1.30.0       # OpenAI API (agent loop)
numpy>=1.24.0        # Dynamics simulation
pyyaml>=6.0          # YAML serialization
rich>=13.0           # Terminal organism inspector
matplotlib>=3.7      # Plot figures
networkx>=3.0        # GRN graph layout
```

---

## 📄 Citation

If you use LEMONOIDS in your research, please cite:

```bibtex
@misc{lemonoids2026,
  title  = {{LEMONOIDS}: A Synthetic Organism Reasoning Benchmark for LLM Agents},
  author = {Turing Team and 👾},
  year   = {2026},
  url    = {https://github.com/RelationRx/rrx-lemonoids},
}
```
