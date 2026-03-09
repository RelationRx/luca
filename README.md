# 🍋 LEMONOIDS

**Synthetic organism reasoning benchmark for LLM agents**
![Example organism — seed 42](assets/org42.png)
A Python package that procedurally generates synthetic biological organisms (gene regulatory networks) and exposes them as a reasoning benchmark for LLM agents.

The world is **unknowable via retrieval** — gene names, module labels, signals, and pathways are all invented. Prior biological knowledge is useless. An agent must reason causally from perturbation experiments to succeed. 🧫

---

## ⚡ Quick Start

```bash
pip install -r requirements.txt

# Smoke test
python -c "from lemonoids import generate_organism; o = generate_organism(seed=0); print(o.id)"

# Full demo (smoke tests + optional agent session)
python demo.py
python demo.py --agent             # requires ANTHROPIC_API_KEY
python demo.py --agent --disease   # disease mode agent session
```

---

## 🔍 Inspector CLI

Inspect organisms in the terminal or as a plot. Run agent sessions and visualise experiment replays.

```bash
# Terminal summary + interactive graph (default seed=42, n_genes=15)
python inspect_organism.py

# Different organism
python inspect_organism.py --seed 7 --n-genes 25

# Save plot to file without opening a window
python inspect_organism.py --seed 7 --save org.png --no-show

# Terminal only (no matplotlib required)
python inspect_organism.py --no-plot

# Disease organism — healthy vs disease comparison figure
python inspect_organism.py --disease --seed 7 --no-show --save disease.png

# Run an agent session and view experiment replay heatmap (requires ANTHROPIC_API_KEY)
python inspect_organism.py --replay --seed 42 --no-show --save replay.png

# Disease mode agent replay with logging and trace output
python inspect_organism.py --replay --disease --seed 42 --budget 15 \
    --log logs/run.json --trace --no-show --save replay.png
# → also auto-generates logs/run.html (self-contained diagnostic report)
```

**CLI flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--seed INT` | 42 | Organism seed |
| `--n-genes INT` | 15 | Number of genes |
| `--n-modules INT` | 4 | Number of modules |
| `--save PATH` | — | Save figure to file |
| `--no-show` | off | Skip interactive plot window |
| `--no-terminal` | off | Skip rich terminal summary |
| `--no-plot` | off | Skip matplotlib figure |
| `--disease` | off | Generate a disease organism |
| `--replay` | off | Run agent session and plot experiment heatmap |
| `--budget INT` | 15 | Experiment budget for replay sessions |
| `--all-genes` | off | Show all genes in replay heatmap (default: observable only) |
| `--log PATH` | — | Save agent session log to JSON |
| `--trace` | off | Print human-readable turn-by-turn trace after replay |

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
from lemonoids import generate_organism
from lemonoids.inspect import print_organism, plot_organism

org = generate_organism(seed=42)
print_organism(org)                          # terminal
plot_organism(org, save_path="org.png")      # figure
```

---

## 🧬 Design Principles

1. **Made-up vocabulary** — gene IDs like `G001`, modules labeled `"charge-flow-regulator"`, signals like `"substrate-X"`. No real gene or pathway names. Distinguishes causal reasoning from retrieval.
2. **Continuous sigmoid dynamics** — `x_i(t+1) = σ(bias_i + Σ W_ij·x_j + signal_terms + ε)`. Values in [0, 1].
3. **Named phenotype readouts** — non-linear summaries like `"expansion-rate"` depending on gene states. The agent sees readout names and values, not raw gene states.
4. **JSON/YAML serialization** — organisms are fully serializable for reproducibility and offline evaluation.
5. **Disease mode** — organisms can be given a malfunction (LOCK_HI/LOCK_LO/PERSIST) that shifts phenotypes away from healthy ranges. Agents must diagnose and rescue.

---

## 📁 Package Structure

```
lemonoids/
├── __init__.py       # Public API
├── schema.py         # Dataclasses: Gene, Module, Signal, Relation, Phenotype,
│                     #   DynamicsConfig, Organism, CellType, Malfunction
├── vocabulary.py     # Word banks for invented biological names + cell types
├── generation.py     # generate_organism(), generate_disease_organism()
├── dynamics.py       # simulate_sigmoid(), compute_phenotypes()
├── experiment.py     # ExperimentSession — budget, interventions, scoring
├── dataset.py        # generate_dataset() — JSON export for offline benchmarking
├── agent.py          # Claude tool definitions + run_agent() agentic loop
├── inspect.py        # plot_organism(), plot_disease_organism(), plot_session()
└── report.py         # print_session_trace(), export_session_html()

demo.py               # Smoke tests + agent demo entry point
inspect_organism.py   # CLI inspector and replay tool
requirements.txt
```

---

## 🔬 Core Concepts

### Organism

An `Organism` contains:
- 🧬 **Genes** — `G001`…`GNNN`, each with an internal ID (`g_001`) and display name (`G001`)
- 🗂️ **Modules** — hidden groupings of genes by functional role (e.g. `"polarity-oscillator"`)
- 📡 **Signals** — external inputs that activate or inhibit target genes (e.g. `"substrate-X"`)
- 🔗 **Relations** — signed weighted edges between genes (`activates` / `inhibits`)
- 📊 **Phenotypes** — named readouts computed as sigmoid of weighted gene sums (e.g. `"expansion-rate"`)
- ⚙️ **Dynamics config** — per-gene bias, input weights, noise sigma

> Modules are **hidden from the agent** — inferring them is part of the challenge.

### Disease Organisms

A disease organism is a healthy organism with one or more **malfunctions** applied:

| Malfunction type | Description |
|-----------------|-------------|
| `LOCK_HI` | Node locked high — bias forced high; activity saturates |
| `LOCK_LO` | Node locked low — bias forced low; activity silenced |
| `PERSIST` | A signal permanently active at amplified strength |

Additional fields on a disease `Organism`:
- `cell_type` — a `CellType` with label and description
- `healthy_baseline` — pre-malfunction gene steady states
- `healthy_phenotype_ranges` — `{label: (lo, hi)}` defining normal phenotype ranges
- `malfunctions` — list of `Malfunction` objects (target, type, severity, description)
- `baseline_state` — the **disease** steady state (what the agent observes)

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
| `BLOCK` | Force node to 0.0 each step (suppress to zero) |
| `BOOST` | Force node to 1.0 each step (saturate to max) |
| `DAMPEN` | Clamp node to ≤ 0.15 after each step (reduce to low) |
| signal `"activate"` | Add `+signal_strength` to target node's input |

---

## 📖 API Reference

### `generate_organism()`

```python
from lemonoids import generate_organism

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

### `generate_disease_organism()`

```python
from lemonoids import generate_disease_organism

org = generate_disease_organism(
    n_genes=15,
    n_modules=4,
    seed=7,
    # All generate_organism() kwargs are accepted
)
```

Generates a healthy organism, assigns a `CellType`, then applies a malfunction (randomly LOCK_HI, LOCK_LO, or PERSIST on a gene or signal that demonstrably shifts at least one phenotype outside its healthy range). Returns a disease `Organism` whose `baseline_state` is the post-malfunction steady state.

```python
from lemonoids.inspect import plot_disease_organism

plot_disease_organism(org, save_path="disease.png")
# Paired bars: grey = healthy baseline, coloured = disease state
# Red highlights on phenotypes outside healthy range
```

---

### `ExperimentSession`

```python
from lemonoids import ExperimentSession

session = ExperimentSession(org, seed=0)  # budget defaults to recommended_budget(org)
```

On init, 2 `PredictionTask`s are generated with hidden ground-truth phenotype values. Tasks use cross-module double-gene interventions that are unlikely to have been directly measured.

#### Methods

**`get_info()`** — 🆓 free
```python
info = session.get_info()
# Returns: gene_names, signals, observable_phenotypes, budget, baseline_phenotypes
# Disease organisms also return: cell_type, cell_type_description,
#   healthy_phenotype_ranges, aberrant_phenotypes
```

**`get_next_prediction_task()`** — 🆓 free
```python
task = session.get_next_prediction_task()
# Returns one task at a time:
#   {task_id, interventions, tasks_remaining, note}
# The next task only unlocks after the current one is submitted via submit_prediction().
# Returns {done: True} when all tasks have been submitted.
```

**`run_experiment(interventions)`** — 💸 costs 1 budget unit
```python
result = session.run_experiment({
    "G005": {"type": "BLOCK"},
    "G012": {"type": "BOOST"},
    "substrate-X": "activate",   # signal label
})
# Returns: phenotypes dict, status, steps, budget_remaining
```

**`submit_prediction(task_id, prediction)`** — 🆓 free
```python
score = session.submit_prediction("task_00", {
    "expansion-rate": 0.72,
    "stress-index": 0.45,
})
# Returns: mse, accuracy (fraction within 0.15 threshold), per-phenotype details
```

**`submit_hypothesis(text)`** — 🆓 free
```python
session.submit_hypothesis("G010 appears to be a master regulator of expansion-rate...")
```

**`test_rescue(interventions)`** — 💸 costs 1 budget unit *(disease mode only)*
```python
result = session.test_rescue({"G007": {"type": "BLOCK"}})
# Returns: phenotypes, per-phenotype in_healthy_range flags,
#          restored_fraction, mse_vs_healthy, budget_remaining
```

**`submit_malfunction_hypothesis(target_name, malfunction_type)`** — 🆓 free *(disease mode only)*
```python
result = session.submit_malfunction_hypothesis("G007", "LOCK_HI")
# malfunction_type: "LOCK_HI" | "LOCK_LO" | "PERSIST"
# One submission only — locked immediately. Unlocks test_rescue().
# Returns: {"stored": True, "note": "..."}
# Score (1.0 exact, 0.5 right target wrong type, 0.0 wrong) revealed via get_summary().
```

**`get_summary()`**
```python
summary = session.get_summary()
# Returns: organism_id, budget_total, budget_used, prediction_results,
#          avg_mse, avg_accuracy, hypothesis, n_experiments
# Disease mode also includes: malfunction_hypothesis, rescue_results
```

---

### `run_agent()`

```python
from lemonoids import run_agent

summary = run_agent(
    session,
    model="claude-opus-4-6",   # or "claude-sonnet-4-6", "gpt-5.1", etc.
    max_turns=50,
    verbose=True,
    disease_mode=None,         # None = auto-detect from session
    log_path="logs/run.json",  # optional: save structured JSON log
)
```

Runs an LLM agent against the session using a tool-use harness. Provider is inferred from the model name (`claude-*` → Anthropic, `gpt-*`/`o1`/`o3` → OpenAI). The system prompt frames the vocabulary as synthetic and instructs the model to reason from perturbation data only.

**Tools available to the agent:**

| Tool | Cost | Description |
|------|------|-------------|
| `get_organism_info` | free | Gene list, signals, phenotypes, baseline |
| `get_next_prediction_task` | free | Reveal next prediction task (one at a time) |
| `run_experiment` | 1 budget | Run perturbation, get phenotype readout |
| `submit_prediction` | free | Score prediction for a task |
| `submit_hypothesis` | free | Store free-text causal hypothesis |
| `test_rescue` *(disease)* | 1 budget | Test rescue intervention vs healthy ranges |
| `submit_malfunction_hypothesis` *(disease)* | free | Diagnose malfunction type and target |

**Agent goals (healthy mode):** phenotype prediction → causal hypothesis

**Agent goals (disease mode):** malfunction diagnosis → rescue → phenotype prediction → causal hypothesis

When `log_path` is provided, a structured JSON log is written with per-turn reasoning text and tool call results. An HTML diagnostic report is auto-generated at the same path with `.html` extension when using the inspector CLI.

---

### Diagnostic Reports

```python
from lemonoids.report import print_session_trace, export_session_html
import json

with open("logs/run.json") as f:
    log = json.load(f)

print_session_trace(log)           # human-readable turn-by-turn trace
export_session_html(log, "run.html")  # self-contained dark-theme HTML report
```

**`print_session_trace`** outputs:
- Per-turn reasoning snippet, tool calls with inputs and results
- For `run_experiment`: Δ from baseline per phenotype, health flags (✓/✗/⚠)
- For `test_rescue`: per-phenotype healthy-range check
- Summary section at end

**`export_session_html`** generates:
- Self-contained HTML with dark theme, collapsible turn cards
- Color-coded tool call results (ok / warn / error)
- Summary table at bottom

**Replay heatmap** (`plot_session`) shows gene states across all experiments with turn labels (T1, T2…) and reasoning snippets when `agent_log` is provided:

```python
from lemonoids.inspect import plot_session
plot_session(session, save_path="replay.png", agent_log=log)
```

---

### `generate_dataset()`

```python
from lemonoids import generate_dataset

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

## 🏆 Benchmark Outcomes

Agent sessions are evaluated on the following outcomes:

**Healthy mode:**

| Outcome | Metric | Notes |
|---------|--------|-------|
| 🎯 Phenotype prediction | MSE, accuracy (±0.15 threshold) | 2 cross-module double-gene tasks, revealed one at a time |
| 💬 Causal hypothesis | Stored free text | Qualitative review |

**Disease mode (additional):**

| Outcome | Metric | Notes |
|---------|--------|-------|
| 🩺 Malfunction diagnosis | Score 0 / 0.5 / 1.0 | 1.0 = exact target + type, 0.5 = right target wrong type; one submission, locked on commit |
| 💊 Rescue quality | Restored fraction, MSE vs healthy | Best rescue result across all `test_rescue` calls |

> **Prediction tasks** are revealed one at a time via `get_next_prediction_task()`. The next task only unlocks after the current prediction is submitted, preventing direct-measurement gaming.

> **Random baseline:** prediction MSE ≈ 0.08.

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
  author = {Gogleva, Anna and others},
  year   = {2026},
  url    = {https://github.com/RelationRx/rrx-lemonoids},
}
```
