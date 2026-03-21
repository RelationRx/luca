# Bring Your Own Agent

LEMONOIDS supports custom agents via a simple Python callable interface. You can benchmark any agent — rule-based, LLM-powered, or otherwise — against the same organisms and scoring as the built-in models.

---

## Interface

Your agent is a Python function with the signature:

```python
def run(session) -> None:
    ...
```

The function receives an `ExperimentSession` and must interact with it before returning. `evaluate.py` handles scoring automatically — you do not need to call `get_summary()`.

**Available session methods:**

| Method | Description |
|--------|-------------|
| `session.get_info()` | Organism description: gene names, baseline phenotypes, observable phenotypes, budget |
| `session.run_experiment(interventions)` | Run a perturbation; costs 1 budget unit |
| `session.get_next_prediction_task()` | Get the next prediction task (returns `{"done": True}` when all submitted) |
| `session.submit_prediction(task_id, values)` | Submit phenotype predictions for a task |
| `session.submit_hypothesis(text)` | Submit a free-text causal summary (optional) |
| `session.submit_malfunction_hypothesis(gene, type)` | Disease mode: submit diagnosis |
| `session.test_rescue(interventions)` | Disease mode: test a rescue intervention |
| `session.budget_used` | Experiments run so far |
| `session.budget` | Total experiment budget |
| `session.is_disease` | True if this is a disease session |

**Intervention format:**
```python
# Single interventions
session.run_experiment({"G001": {"type": "BLOCK"}})
session.run_experiment({"G001": {"type": "BOOST"}, "G005": {"type": "DAMPEN"}})

# Signal activation
session.run_experiment({"flux-Z": {"type": "activate"}})
```

**Intervention types:** `BLOCK` (suppress to 0.0) · `BOOST` (saturate to 1.0) · `DAMPEN` (clamp to ≤0.15)

**Malfunction types** (disease mode): `LOCK_HI` · `LOCK_LO` · `PERSIST`

---

## Minimal example

```python
# my_agent.py

def run(session) -> None:
    """Block every gene once, then predict additively."""
    info = session.get_info()
    baseline = info["baseline_phenotypes"]
    phenotypes = info["observable_phenotypes"]

    # Exploration phase
    effects = {}
    for gene in info["gene_names"]:
        if session.budget_used >= session.budget - 2:
            break
        result = session.run_experiment({gene: {"type": "BLOCK"}})
        if "error" not in result:
            effects[gene] = {
                p: result["phenotypes"].get(p, baseline[p]) - baseline[p]
                for p in phenotypes
            }

    # Prediction phase
    while True:
        task = session.get_next_prediction_task()
        if task.get("done"):
            break
        prediction = {}
        for p in phenotypes:
            pred = baseline[p]
            for gene, iv in task["interventions"].items():
                sign = -1.0 if iv["type"] == "BLOCK" else 1.0
                pred += sign * effects.get(gene, {}).get(p, 0.0)
            prediction[p] = max(0.0, min(1.0, pred))
        session.submit_prediction(task["task_id"], prediction)
```

Run it:
```bash
python evaluate.py --agent my_agent.py:run --n 5
python evaluate.py --agent my_agent.py:run --difficulty hard --disease
python evaluate.py --agent my_agent.py:run --agent-name my-additive-agent --n 20
```

---

## Disease mode

If `session.is_disease` is True, two extra steps are available after predictions:

```python
def run(session) -> None:
    # ... exploration and prediction as above ...

    if session.is_disease:
        # Diagnosis: identify the malfunctioning gene and type
        session.submit_malfunction_hypothesis("G007", "LOCK_HI")

        # Rescue: test an intervention to restore healthy phenotypes
        session.test_rescue({"G007": {"type": "BLOCK"}})
```

`submit_malfunction_hypothesis` must be called before `test_rescue`. The hypothesis is locked on first call. Scoring is revealed at the end via the benchmark runner, not during the session.

---

## Accessing `get_info()` fields

```python
info = session.get_info()

info["gene_names"]            # list of observable gene names, e.g. ["G001", "G003", ...]
info["baseline_phenotypes"]   # dict of phenotype label → baseline value, e.g. {"standby-level": 0.52}
info["observable_phenotypes"] # list of phenotype labels
info["budget"]                # total experiment budget (int)
info["description"]           # full organism description text (same as agent system prompt)

# Disease mode only:
info["aberrant_phenotypes"]   # list of phenotype labels that are outside healthy range
```

---

## Using an LLM via a hosted API

For open-source or third-party models served via an OpenAI-compatible API (Together AI, Fireworks, Ollama, vLLM, etc.):

```python
# openai_compat_agent.py
import os
import openai

def run(session) -> None:
    client = openai.OpenAI(
        api_key=os.environ["TOGETHER_API_KEY"],
        base_url="https://api.together.xyz/v1",
    )
    # build tool definitions from session.get_info() and run your own agent loop
    ...
```

For Claude or OpenAI models, the built-in `run_agent()` (invoked via `--model`) already handles tool definitions, budget enforcement, and logging. Use `--agent` when you need a custom loop or a model not natively supported.

---

## Results and logging

Results are written to `results/<timestamp>/` alongside built-in model results in the same JSONL format. Per-session logs go to `results/<timestamp>/logs/<name>_seed*.json`.

Use `--agent-name` to set a clean name in the results:
```bash
python evaluate.py --agent my_agent.py:run --agent-name llama-3.3-70b --n 20
```
