# 🍋 LEMONOIDS — API Reference

## `generate_organism()`

```python
from lemonoids import generate_organism

org = generate_organism(
    n_genes=20,
    n_modules=4,
    n_signals=3,
    n_phenotypes=3,
    difficulty="medium",        # "easy"/"medium"/"hard" or biological aliases
    observability=0.6,          # fraction of genes visible to agent (overrides preset)
    intra_module_density=0.4,   # edge probability within modules
    inter_module_density=0.08,  # edge probability between modules
    inhibition_fraction=0.3,    # fraction of edges that are inhibitory
    n_ffls=2,                   # feed-forward loops to inject
    n_feedback=2,               # feedback edges to inject
    noise_sigma=0.01,
    sigmoid_steepness=None,     # sigmoid gain (overrides preset)
    latent_fraction=None,       # fraction of genes never observable or targetable
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

## `generate_disease_organism()`

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

| Malfunction type | Description |
|-----------------|-------------|
| `LOCK_HI` | Node locked high — bias forced high; activity saturates |
| `LOCK_LO` | Node locked low — bias forced low; activity silenced |
| `PERSIST` | A signal permanently active at amplified strength |

Additional fields on a disease `Organism`: `cell_type`, `healthy_baseline`, `healthy_phenotype_ranges`, `malfunctions`.

```python
from lemonoids.inspect import plot_disease_organism, plot_disease_comparison

plot_disease_organism(org, save_path="disease.png")
# Single-panel: gene activity + phenotype bars, disease state coloured,
# healthy baseline in grey, aberrant phenotypes highlighted

plot_disease_comparison(org, save_path="compare.png")
# Side-by-side healthy vs disease GRN + bar chart; malfunction node in magenta
```

---

## `ExperimentSession`

```python
from lemonoids import ExperimentSession

session = ExperimentSession(org, seed=0)  # budget defaults to recommended_budget(org)
```

On init, 2 `PredictionTask`s are generated with hidden ground-truth phenotype values. Tasks use cross-module double-gene interventions that are unlikely to have been directly measured.

### Methods

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
# Returns: organism_id, budget_total, budget_used, n_experiments,
#          prediction_results, avg_mse, avg_accuracy, hypothesis
# Disease mode also includes: malfunction_hypothesis, rescue_results
```

---

## `run_agent()`

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

## Diagnostic Reports

```python
from lemonoids.report import print_session_trace, export_session_html
import json

with open("logs/run.json") as f:
    log = json.load(f)

print_session_trace(log)              # human-readable turn-by-turn trace
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

---

## `generate_dataset()`

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
