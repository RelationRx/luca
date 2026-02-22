# 🍋 LEMONS

**Life-like Experimental Mechanistic Organism Network Suite**

A Python package that procedurally generates synthetic biological organisms (gene regulatory networks) and exposes them as a reasoning benchmark for LLM agents.

The world is **unknowable via retrieval** — gene names, module labels, signals, and pathways are all invented. Prior biological knowledge is useless. An agent must reason causally from perturbation experiments to succeed. 🧫

---

## ⚡ Quick Start

```bash
pip install -r requirements.txt

# Smoke test
python -c "from bioworld import generate_organism; o = generate_organism(seed=0); print(o.id)"

# Full demo (smoke tests + optional agent session)
python demo.py
python demo.py --agent   # requires ANTHROPIC_API_KEY
```

---

## 🔍 Inspector

Quickly inspect any organism in the terminal or as a plot.

```bash
# Terminal summary + interactive graph (default seed=42, n_genes=15)
python inspect_organism.py

# Different organism
python inspect_organism.py --seed 7 --n-genes 25

# Save plot to file without opening a window
python inspect_organism.py --seed 7 --save org.png --no-show

# Terminal only (no matplotlib required)
python inspect_organism.py --no-plot
```

The **terminal view** (via `rich`) shows:
- 🗂️ Module membership, color-coded by functional group
- 🧬 Baseline gene states as block bar charts, with 👁 markers for observable genes
- 📡 Signals with mode and targets
- 📊 Phenotype baseline values

The **graph figure** (via `matplotlib` + `networkx`) shows:
- Translucent colored blobs behind each module cluster
- Green arrows = activating edges, red dashed = inhibiting (width = strength)
- Yellow diamonds = signal inputs
- White-bordered nodes = observable genes
- Right panel: horizontal bar chart of baseline gene states + phenotype values

**Programmatic usage:**
```python
from bioworld import generate_organism
from bioworld.inspect import print_organism, plot_organism

org = generate_organism(seed=42)
print_organism(org)                          # terminal
plot_organism(org, save_path="org.png")      # figure
```

---

## 🧬 Design Principles

1. **Made-up vocabulary** — gene IDs like `G001`, modules labeled `"ion-flux-regulator"`, signals like `"nutrient-X"`. No real gene or pathway names. Distinguishes causal reasoning from retrieval.
2. **Continuous sigmoid dynamics** — `x_i(t+1) = σ(bias_i + Σ W_ij·x_j + signal_terms + ε)`. Values in [0, 1].
3. **Named phenotype readouts** — non-linear summaries like `"growth-rate"` depending on gene states. The agent sees readout names and values, not raw gene states.
4. **JSON/YAML serialization** — organisms are fully serializable for reproducibility and offline evaluation.

---

## 📁 Package Structure

```
bioworld/
├── __init__.py       # Public API
├── schema.py         # Dataclasses: Gene, Module, Signal, Relation, Phenotype, Organism
├── vocabulary.py     # Word banks for invented biological names
├── generation.py     # generate_organism() — GRN construction, dynamics params
├── dynamics.py       # simulate_sigmoid() — discrete-time continuous dynamics
├── experiment.py     # ExperimentSession — budget, interventions, scoring
├── dataset.py        # generate_dataset() — JSON export for offline benchmarking
└── agent.py          # Claude tool definitions + agentic loop

demo.py               # Smoke tests + agent demo entry point
requirements.txt
```

---

## 🔬 Core Concepts

### Organism

An `Organism` contains:
- 🧬 **Genes** — `G001`…`GNNN`, each with an internal ID (`g_001`) and display name (`G001`)
- 🗂️ **Modules** — hidden groupings of genes by functional role (e.g. `"redox-oscillator"`)
- 📡 **Signals** — external inputs that activate or inhibit target genes (e.g. `"nutrient-X"`)
- 🔗 **Relations** — signed weighted edges between genes (`activates` / `inhibits`)
- 📊 **Phenotypes** — named readouts computed as sigmoid of weighted gene sums (e.g. `"growth-rate"`)
- ⚙️ **Dynamics config** — per-gene bias, input weights, noise sigma

> Modules are **hidden from the agent** — inferring them is part of the challenge.

### Dynamics

Each timestep:
```
z_i = bias_i + Σ_j W_ij · x_j(t) + signal_inputs_i
x_i(t+1) = σ(z_i) + ε_i       ε_i ~ N(0, σ_noise)
```

Convergence is detected on the deterministic trajectory (`||Δx||∞ < 1e-3`), with noise added on top for the returned state. Max 500 steps.

### Interventions

| Type | Effect |
|------|--------|
| `KO` 💀 | Force gene to 0.0 (knockout) |
| `OE` 🔥 | Force gene to 1.0 (overexpression) |
| `KD` 🔇 | Clamp gene to ≤ 0.15 after each step (knockdown) |
| signal activate 📶 | Add `+signal_strength` to target gene's input |

---

## 📖 API Reference

### `generate_organism()`

```python
from bioworld import generate_organism

org = generate_organism(
    n_genes=20,
    n_modules=4,
    n_signals=3,
    n_phenotypes=3,
    observability=0.6,          # fraction of genes visible to agent
    intra_module_density=0.4,   # edge probability within modules
    inter_module_density=0.08,  # edge probability between modules
    inhibition_fraction=0.3,    # fraction of edges that are inhibitory
    n_ffls=2,                   # feed-forward loops to inject
    n_feedback=2,               # feedback edges to inject
    noise_sigma=0.01,
    seed=42,
)
```

Returns an `Organism` with a computed `baseline_state`.

**Serialization:**
```python
json_str = org.to_json()
org2 = Organism.from_json(json_str)

yaml_str = org.to_yaml()
org3 = Organism.from_yaml(yaml_str)
```

---

### `ExperimentSession`

```python
from bioworld import ExperimentSession

session = ExperimentSession(org, budget=20, seed=0)
```

On init, 5 `PredictionTask`s are generated with hidden ground-truth phenotype values.

#### Methods

**`get_info()`** — 🆓 free
```python
info = session.get_info()
# Returns: gene_names, signals, observable_phenotypes, budget,
#          baseline_phenotypes, prediction_tasks
```

**`run_experiment(interventions)`** — 💸 costs 1 budget unit
```python
result = session.run_experiment({
    "G005": {"type": "KO"},
    "G012": {"type": "OE"},
    "nutrient-X": "activate",   # signal label
})
# Returns: phenotypes dict, status, steps, budget_remaining
```

**`submit_prediction(task_id, prediction)`** — 🆓 free
```python
score = session.submit_prediction("task_00", {
    "growth-rate": 0.72,
    "stress-index": 0.45,
})
# Returns: mse, accuracy (fraction within 0.15 threshold), details
```

**`submit_module_assignment(assignments)`** — 🆓 free
```python
score = session.submit_module_assignment({
    "G001": "module-A",
    "G002": "module-A",
    "G003": "module-B",
    # ...
})
# Returns: ARI, NMI vs ground truth
```

**`submit_hypothesis(text)`** — 🆓 free
```python
session.submit_hypothesis("G010 appears to be a master regulator of stress-index...")
```

**`get_summary()`**
```python
summary = session.get_summary()
# Returns: all scores, budget_used, experiment count
```

---

### `generate_dataset()`

```python
from bioworld import generate_dataset

paths = generate_dataset(
    n_organisms=50,
    experiments_per_organism=10,
    complexity_range={"n_genes": (10, 30), "n_modules": (3, 6)},
    output_path="my_dataset/",
    seed=42,
)
# Writes: my_dataset/organisms.json, my_dataset/experiments.json
```

- 🧬 `organisms.json` — serialized organisms including hidden ground-truth modules
- 🧪 `experiments.json` — `{organism_id, experiment_id, interventions, result}` records

---

### `run_agent()`

```python
from bioworld.agent import run_agent

summary = run_agent(
    session,
    model="claude-opus-4-6",   # or "claude-sonnet-4-6"
    max_turns=50,
    verbose=True,
)
```

Runs Claude with 5 tools against the session. The system prompt explicitly frames the vocabulary as synthetic and instructs the model to reason from perturbation data only — prior biological knowledge is counterproductive. 🚫🔬

---

## 🏆 Benchmark Tasks

An agent session is scored on three axes:

| Task | Metric | How to score well |
|------|--------|-------------------|
| 🎯 Phenotype prediction | MSE, accuracy (±0.15) | Run targeted KO/OE experiments; match observed phenotype shifts to task interventions |
| 🗂️ Module inference | ARI, NMI vs ground truth | Run co-perturbation experiments; cluster genes by correlated phenotype responses |
| 💬 Hypothesis quality | Stored free text | Qualitative review |

> **Random baseline:** prediction MSE ≈ 0.08, module ARI ≈ 0.

---

## 📦 Dependencies

```
anthropic>=0.40.0    # Claude API (agent loop only)
numpy>=1.24.0        # Dynamics simulation
scikit-learn>=1.3.0  # ARI/NMI scoring
pyyaml>=6.0          # YAML serialization
```
