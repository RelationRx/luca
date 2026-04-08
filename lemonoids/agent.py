"""Claude agent harness for Lemonoids reasoning benchmark."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from typing import Any

import anthropic

# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def _git_commit() -> str | None:
    """Return the current git HEAD commit hash, or None if unavailable."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None


def _prompt_hash(prompt: str) -> str:
    """Short SHA-256 hex digest of a prompt string."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# API call helper
# ---------------------------------------------------------------------------

_API_TIMEOUT = 120.0   # seconds per request
_API_RETRIES = 6       # attempts before giving up
_API_RETRY_WAIT = 15   # seconds between retries


def _with_retry(fn, retryable_exc: tuple, *args, **kwargs):
    """Call fn(*args, **kwargs) up to _API_RETRIES times on retryable_exc errors."""
    for attempt in range(_API_RETRIES):
        try:
            return fn(*args, **kwargs)
        except retryable_exc as exc:
            if attempt == _API_RETRIES - 1:
                raise
            print(f"\n[agent] API error ({exc.__class__.__name__}), retrying in {_API_RETRY_WAIT}s "
                  f"(attempt {attempt + 1}/{_API_RETRIES})...")
            time.sleep(_API_RETRY_WAIT)
        except anthropic.APIStatusError as exc:
            # Retry on transient server errors (529 overloaded, 503 unavailable)
            if exc.status_code not in (500, 503, 529) or attempt == _API_RETRIES - 1:
                raise
            wait = _API_RETRY_WAIT * (attempt + 1)  # back off: 10s, 20s, 30s
            print(f"\n[agent] API overloaded (HTTP {exc.status_code}), retrying in {wait}s "
                  f"(attempt {attempt + 1}/{_API_RETRIES})...")
            time.sleep(wait)

from .experiment import ExperimentSession

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

DISEASE_TOOLS: list[dict] = [
    {
        "name": "test_rescue",
        "description": (
            "Test whether a proposed intervention restores aberrant phenotypes to healthy ranges. "
            "Costs 1 budget. Requires submit_malfunction_hypothesis() to be called first. "
            "Runs the organism from the disease baseline with your intervention "
            "and reports per-phenotype restoration status and MSE vs healthy baseline."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "interventions": {
                    "type": "object",
                    "description": (
                        "Map of target → intervention. Gene names (e.g. 'G007') with values "
                        "like {\"type\": \"BLOCK\"}, {\"type\": \"BOOST\"}, {\"type\": \"DAMPEN\"}, "
                        "or signal labels with value 'activate'."
                    ),
                    "additionalProperties": True,
                },
            },
            "required": ["interventions"],
        },
    },
    {
        "name": "submit_malfunction_hypothesis",
        "description": (
            "Submit your hypothesis about which gene or signal is malfunctioning and how. "
            "No budget cost. One submission only — locked immediately. "
            "Unlocks test_rescue(). Score is NOT returned here; it is revealed at session end. "
            "Commit only when confident — you cannot revise this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "Gene name (e.g. 'G007') or signal label that you believe is malfunctioning.",
                },
                "malfunction_type": {
                    "type": "string",
                    "enum": ["LOCK_HI", "LOCK_LO", "PERSIST"],
                    "description": (
                        "LOCK_HI = node locked in high state, "
                        "LOCK_LO = node locked in low state, "
                        "PERSIST = external signal persistently active."
                    ),
                },
            },
            "required": ["target_name", "malfunction_type"],
        },
    },
]

TOOLS: list[dict] = [
    {
        "name": "get_organism_info",
        "description": (
            "Retrieve information about the synthetic organism: gene names, available signals, "
            "observable phenotypes, budget, and baseline phenotype values. "
            "This call is free (no budget cost)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_next_prediction_task",
        "description": (
            "Reveal the next prediction task. Tasks are given one at a time — "
            "you must submit your prediction for the current task before the next one unlocks. "
            "Each task applies two simultaneous gene interventions from different modules, "
            "combinations you are unlikely to have directly measured. "
            "Call this when you have built enough causal understanding to predict outcomes. "
            "No budget cost."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_experiment",
        "description": (
            "Run a perturbation experiment on the organism. Costs 1 unit of budget. "
            "Specify gene interventions (BLOCK=suppress to zero, BOOST=saturate to max, DAMPEN=reduce to low) "
            "and/or signal activations. Returns phenotype readouts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "interventions": {
                    "type": "object",
                    "description": (
                        "Map of target → intervention. Targets can be gene names (e.g. 'G001') "
                        "with values like {\"type\": \"BLOCK\"}, {\"type\": \"BOOST\"}, {\"type\": \"DAMPEN\"}, "
                        "or signal labels (e.g. 'nutrient-X') with value 'activate'."
                    ),
                    "additionalProperties": True,
                },
            },
            "required": ["interventions"],
        },
    },
    {
        "name": "submit_prediction",
        "description": (
            "Submit a prediction for one of the prediction tasks. No budget cost. "
            "You MUST provide both 'task_id' and 'prediction'. "
            "'prediction' is a JSON object mapping each phenotype label to a float in [0.0, 1.0]. "
            "Example: {\"task_id\": \"task_00\", \"prediction\": {\"stress-index\": 0.4, \"integrity-index\": 0.6}}. "
            "Returns MSE and accuracy (fraction within 0.10 threshold)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID from get_next_prediction_task (e.g. 'task_00').",
                },
                "prediction": {
                    "type": "object",
                    "description": (
                        "Map of phenotype label → predicted float value [0.0, 1.0]. "
                        "Must include ALL observable phenotypes. "
                        "Example: {\"stress-index\": 0.4, \"integrity-index\": 0.6, \"recovery-index\": 0.5}"
                    ),
                    "additionalProperties": {"type": "number"},
                },
            },
            "required": ["task_id", "prediction"],
        },
    },
    {
        "name": "submit_hypothesis",
        "description": (
            "Submit a free-text hypothesis about the organism's regulatory structure, "
            "key genes, or signaling logic. No budget cost. Stored for review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Your hypothesis about the organism's biology.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "submit_network",
        "description": (
            "Submit your reconstructed gene→phenotype network as a list of edges inferred "
            "from your experiments. No budget cost. Can be called once. "
            "Precision/recall/F1 against ground truth are revealed at session end via get_summary(). "
            "Include all gene→phenotype relationships you are confident about. "
            "Direction ('activates' or 'inhibits') is optional but scored if provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "edges": {
                    "type": "array",
                    "description": "List of inferred gene→phenotype edges.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "gene": {
                                "type": "string",
                                "description": "Gene name, e.g. 'G007'.",
                            },
                            "phenotype": {
                                "type": "string",
                                "description": "Phenotype label, e.g. 'adaptation-score'.",
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["activates", "inhibits"],
                                "description": "Optional: whether this gene activates or inhibits the phenotype.",
                            },
                        },
                        "required": ["gene", "phenotype"],
                    },
                },
            },
            "required": ["edges"],
        },
    },
]

# ---------------------------------------------------------------------------
# Task-based tool filtering
# ---------------------------------------------------------------------------

_PREDICT_TOOLS = {"get_next_prediction_task", "submit_prediction"}
_DIAGNOSE_TOOLS = {"submit_malfunction_hypothesis"}
_RESCUE_TOOLS = {"test_rescue"}


def _active_tool_list(
    disease_mode: bool,
    active_tasks: frozenset[str],
) -> list[dict]:
    """
    Build the tool list for an agent session given which task components are active.

    Always included: get_organism_info, run_experiment, submit_hypothesis, submit_network.
    Conditionally included:
      predict  → get_next_prediction_task, submit_prediction
      diagnose → submit_malfunction_hypothesis  (disease only)
      rescue   → test_rescue                   (disease only)
    """
    result = [t for t in TOOLS if t["name"] not in _PREDICT_TOOLS]
    if "predict" in active_tasks:
        result += [t for t in TOOLS if t["name"] in _PREDICT_TOOLS]
    if disease_mode:
        if "diagnose" in active_tasks:
            result += [t for t in DISEASE_TOOLS if t["name"] in _DIAGNOSE_TOOLS]
        if "rescue" in active_tasks:
            result += [t for t in DISEASE_TOOLS if t["name"] in _RESCUE_TOOLS]
    return result


# ---------------------------------------------------------------------------
# System prompt (built dynamically to match active_tasks)
# ---------------------------------------------------------------------------

_CRITICAL_BLOCK = """\
CRITICAL: All gene names (e.g. G001, G042), signal labels (e.g. "nutrient-X"), and phenotype \
names (e.g. "growth-rate") are INVENTED VOCABULARY. They do NOT correspond to any real \
biological system. Prior biological knowledge is IRRELEVANT and may mislead you. \
The only valid path to understanding this organism is systematic causal reasoning \
from perturbation experiments."""

_EXPERIMENT_TIPS = """\
Strategy tips:
- Single-gene BLOCK/BOOST experiments first — identify which genes affect which phenotypes.
- BLOCK and BOOST of the same gene producing opposite phenotype shifts is strong causal evidence.
- Do not exhaust the full gene list — stop experimenting when you have a working causal model.

Always call get_organism_info() first."""


def _build_system_prompt(disease_mode: bool, active_tasks: frozenset[str]) -> str:
    """Build a system prompt tailored to the active task components."""
    lines: list[str] = []

    if disease_mode:
        lines.append(
            "You are a computational biologist studying a *de novo* synthetic organism "
            "that is exhibiting a diseased state."
        )
    else:
        lines.append(
            "You are a computational biologist studying a *de novo* synthetic organism."
        )

    lines.append("")
    lines.append(_CRITICAL_BLOCK)

    if disease_mode:
        lines.append("")
        lines.append(
            "DISEASE CONTEXT: This cell exhibits aberrant phenotypes compared to its healthy "
            "baseline ranges. The regulatory network has a single malfunction — either a node "
            "locked high (LOCK_HI), a node locked low (LOCK_LO), or a persistently active "
            "external signal (PERSIST). Your job is to identify it and restore healthy phenotypes."
        )

    # PRIMARY GOALS — only list what's active
    goals: list[str] = []
    if disease_mode:
        if "diagnose" in active_tasks:
            goals.append(
                "Malfunction diagnosis — identify which gene or signal is broken and how "
                "(LOCK_HI / LOCK_LO / PERSIST). Submit via submit_malfunction_hypothesis()."
            )
        if "rescue" in active_tasks:
            goals.append(
                "Rescue — design an intervention that restores aberrant phenotypes to healthy "
                "ranges. Test it via test_rescue()."
            )
    if "predict" in active_tasks:
        goals.append(
            "Phenotype prediction — accurately predict phenotype outcomes under novel "
            "multi-gene interventions. This requires building a real causal model, not guessing."
        )
    goals.append(
        "Causal hypothesis — submit a concise, evidence-based hypothesis naming which genes "
        "regulate which phenotypes and how."
    )

    lines.append("")
    lines.append("PRIMARY GOALS (in order of importance):")
    for i, g in enumerate(goals, 1):
        lines.append(f"{i}. {g}")

    # WORKFLOW
    lines.append("")
    lines.append("WORKFLOW:")
    step = 1
    lines.append(f"{step}. Call get_organism_info() to understand the gene set, signals, phenotypes, and baseline.")
    step += 1
    if disease_mode:
        lines.append(
            f"{step}. Run perturbation experiments targeting genes that affect the aberrant "
            "phenotypes to localise the fault."
        )
    else:
        lines.append(
            f"{step}. Run perturbation experiments (BLOCK, BOOST, DAMPEN, signal activations) "
            "to map gene→phenotype causal relationships. Focus on genes that move phenotypes; "
            "note direction and magnitude."
        )
    step += 1
    if disease_mode and "diagnose" in active_tasks:
        lines.append(
            f"{step}. When confident, submit your malfunction hypothesis via "
            "submit_malfunction_hypothesis(). This is a one-time, irreversible commitment — "
            "it locks immediately and unlocks test_rescue(). Score is revealed at session end."
        )
        step += 1
    if disease_mode and "rescue" in active_tasks:
        if "diagnose" not in active_tasks:
            lines.append(
                f"{step}. NOTE: test_rescue() is available but requires a malfunction hypothesis "
                "to be submitted first. You do not have submit_malfunction_hypothesis() in this "
                "session — rescue will not be possible."
            )
        else:
            lines.append(f"{step}. Test rescue interventions with test_rescue() (costs 1 budget each).")
        step += 1
    if "predict" in active_tasks:
        lines.append(
            f"{step}. When you have a working causal model, call get_next_prediction_task() to "
            "receive one prediction task at a time. Submit your prediction via submit_prediction(), "
            "then call get_next_prediction_task() again for the next task."
        )
        step += 1
    lines.append(f"{step}. Submit your final causal hypothesis via submit_hypothesis().")
    step += 1
    lines.append(
        f"{step}. Submit your reconstructed gene→phenotype network via submit_network(). "
        "List every gene→phenotype edge you are confident about, with direction if known. "
        "This is scored against ground truth at session end."
    )

    # Strategy tips
    lines.append("")
    if disease_mode:
        lines.append(
            "Strategy tips:\n"
            "- LOCK_HI (node locked high): BLOCK or DAMPEN of that node should reduce overactive phenotypes.\n"
            "- LOCK_LO (node locked low): BOOST of that node should restore under-active phenotypes.\n"
            "- PERSIST (signal persistently active): the signal is always on — BLOCK of its direct targets may help.\n"
            "- Aberrant phenotypes are your compass — focus experiments on genes that move them.\n"
            "- BUDGET MANAGEMENT IS CRITICAL: Reserve at least 4 budget units for rescue tests"
            + (" and prediction tasks" if "predict" in active_tasks else "")
            + ". After 5-8 targeted experiments you should be ready to commit your malfunction hypothesis.\n"
            "- Commit to your hypothesis only when the evidence is clear — you cannot revise it."
        )
    else:
        budget_tip = (
            "- BUDGET MANAGEMENT IS CRITICAL: Reserve at least 3 budget units for prediction tasks. "
            "After 5-10 single-gene experiments you should have enough signal.\n"
            "- Call get_next_prediction_task() early — ideally with 5+ budget remaining.\n"
            "- Prediction tasks involve two simultaneous cross-module interventions. Reason from "
            "your model: predict each phenotype based on the combined effect of both genes.\n"
            "- Do not guess 0.5 — every prediction should be grounded in experimental evidence."
        ) if "predict" in active_tasks else (
            "- BUDGET MANAGEMENT IS CRITICAL: After 5-10 single-gene experiments you should "
            "have enough signal to submit a strong causal hypothesis."
        )
        lines.append(
            "Strategy tips:\n"
            "- Single-gene BLOCK/BOOST experiments first — identify which genes affect which phenotypes.\n"
            "- BLOCK and BOOST of the same gene producing opposite phenotype shifts is strong causal evidence.\n"
            + budget_tip
        )

    lines.append("")
    lines.append("Always call get_organism_info() first.")

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# OpenAI tool schema conversion
# ---------------------------------------------------------------------------


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic-style tool schemas to OpenAI function-calling format."""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })
    return result


# ---------------------------------------------------------------------------
# Tool input normalisation
# ---------------------------------------------------------------------------
# These helpers sanitise tool call arguments before dispatch. They exist
# primarily to handle non-standard formats produced by some models (notably
# gpt-5.1) that deviate from the declared tool schemas. If a model is
# well-behaved, the normalisation is a no-op.
# To remove model-specific compat: delete _normalise_interventions and inline
# the trivial JSON-unwrap logic back into dispatch_tool.


def _normalise_interventions(raw: Any) -> dict[str, Any] | str:
    """
    Convert any intervention format a model might send into the canonical
    ``{gene_name: {"type": "BLOCK"|"BOOST"|"DAMPEN"}}`` dict.

    Handles:
    - Correct dict format (no-op)
    - JSON string (unwrap)
    - List format used by some models, e.g.
      ``[{"gene": "G010", "mode": "BOOST"}, ...]``
      or ``[{"target": "G001", "action": "BLOCK"}]``

    Returns an error string if the input cannot be parsed.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return f"interventions must be an object, got string: {raw!r}"

    if isinstance(raw, dict):
        return raw  # canonical format — no-op

    if isinstance(raw, list):
        # gpt-5.1 compat: list of per-gene dicts with varying key names
        normalised: dict[str, Any] = {}
        for item in raw:
            target = item.get("target") or item.get("gene") or item.get("name")
            action = (
                item.get("action") or item.get("mode")
                or item.get("intervention") or item.get("type")
            )
            if target and action and action.upper() in ("BLOCK", "BOOST", "DAMPEN"):
                normalised[target] = {"type": action.upper()}
        return normalised

    return {}


def _normalise_prediction(tool_input: dict) -> dict[str, float] | None:
    """
    Extract the prediction dict from a submit_prediction tool call.

    Handles:
    - Correct format: ``{"task_id": ..., "prediction": {label: float, ...}}``
    - Alternative key ``"predictions"`` (some models)
    - JSON string value
    - Flat structure: ``{"task_id": ..., "stress-index": 0.4, ...}``
      (gpt-5.1 compat: model flattens phenotype values into top-level keys)

    Returns None if no prediction values could be found.
    """
    prediction = tool_input.get("prediction") or tool_input.get("predictions")
    if isinstance(prediction, str):
        try:
            prediction = json.loads(prediction)
        except json.JSONDecodeError:
            prediction = None
    if not prediction:
        # gpt-5.1 compat: try flat top-level numeric values
        prediction = {
            k: float(v) for k, v in tool_input.items()
            if k != "task_id" and isinstance(v, (int, float))
        } or None
    return prediction or None


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def dispatch_tool(session: ExperimentSession, tool_name: str, tool_input: dict) -> Any:
    """Route a tool call to the session."""
    if tool_name == "get_organism_info":
        return session.get_info()
    elif tool_name == "get_next_prediction_task":
        return session.get_next_prediction_task()
    elif tool_name == "run_experiment":
        raw = tool_input.get("interventions") or tool_input.get("gene_interventions", {})
        interventions = _normalise_interventions(raw)
        if isinstance(interventions, str):
            return {"error": interventions}
        return session.run_experiment(interventions)
    elif tool_name == "submit_prediction":
        prediction = _normalise_prediction(tool_input)
        if prediction is None:
            return {
                "error": (
                    "Missing required parameter 'prediction'. "
                    "You MUST include a 'prediction' object with all phenotype labels. "
                    "Example: {\"task_id\": \"task_00\", "
                    "\"prediction\": {\"<label>\": <float>, ...}}"
                )
            }
        return session.submit_prediction(tool_input["task_id"], prediction)
    elif tool_name == "submit_hypothesis":
        return session.submit_hypothesis(tool_input["text"])
    elif tool_name == "submit_network":
        return session.submit_network(tool_input.get("edges", []))
    elif tool_name == "test_rescue":
        raw = tool_input.get("interventions", {})
        interventions = _normalise_interventions(raw)
        if isinstance(interventions, str):
            return {"error": interventions}
        return session.test_rescue(interventions)
    elif tool_name == "submit_malfunction_hypothesis":
        return session.submit_malfunction_hypothesis(
            tool_input["target_name"],
            tool_input["malfunction_type"],
        )
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def _serialize_block(block) -> dict:
    """Convert an API content block (TextBlock / ToolUseBlock) to a plain dict."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": block.type}


def _run_agent_anthropic(
    session: ExperimentSession,
    model: str = "claude-opus-4-6",
    max_turns: int = 50,
    verbose: bool = True,
    disease_mode: bool | None = None,
    log_path: str | None = None,
    active_tasks: frozenset[str] | None = None,
    max_tokens_per_turn: int | None = None,
) -> dict[str, Any]:
    """
    Run an Anthropic Claude model on a Lemonoids ExperimentSession.

    disease_mode: if None, auto-detected from session.is_disease.
    log_path: if provided, write a structured JSON log to this path.
    active_tasks: subset of {"predict", "diagnose", "rescue"} (default: all).
    Returns the session summary after the agent finishes or budget is exhausted.
    """
    import datetime, os
    client = anthropic.Anthropic(timeout=_API_TIMEOUT)
    _anthropic_retryable = (anthropic.APITimeoutError, anthropic.APIConnectionError)

    if disease_mode is None:
        disease_mode = session.is_disease
    if active_tasks is None:
        active_tasks = frozenset({"predict", "diagnose", "rescue"})

    active_tools = _active_tool_list(disease_mode, active_tasks)
    system_prompt = _build_system_prompt(disease_mode, active_tasks)

    # ── Log initialisation ────────────────────────────────────────────────

    log: dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "organism_id": session.organism.id,
            "seed": session.organism.seed,
            "n_genes": len(session.organism.genes),
            "budget": session.budget,
            "disease_mode": disease_mode,
            "active_tasks": sorted(active_tasks),
            "generation_commit": _git_commit(),
            "system_prompt_hash": _prompt_hash(system_prompt),
            "max_tokens_per_turn": max_tokens_per_turn or 16384,
            "max_turns": max_turns,
        },
        "turns": [],
        "summary": None,
    }

    messages: list[dict] = []

    if disease_mode:
        messages.append({
            "role": "user",
            "content": (
                "A diseased cell has been prepared for analysis. "
                "Its regulatory network has malfunctioned, producing aberrant phenotypes. "
                "Your task is to identify the malfunction, design rescue interventions, "
                "predict the phenotype tasks, and submit your hypothesis. "
                "Budget is limited — reason carefully. Begin."
            ),
        })
    else:
        messages.append({
            "role": "user",
            "content": (
                "A new synthetic organism has been prepared for you. "
                "Your task is to probe it with experiments, predict the given phenotype tasks, "
                "and submit your best hypothesis about its regulatory structure. "
                "Budget is limited — reason carefully. Begin."
            ),
        })

    for turn in range(max_turns):
        if verbose:
            print(f"\n[turn {turn + 1}/{max_turns}] Calling {model}...")

        response = _with_retry(
            client.messages.create, _anthropic_retryable,
            model=model,
            max_tokens=max_tokens_per_turn or 16384,
            system=system_prompt,
            tools=active_tools,
            messages=messages,
        )

        if verbose:
            print(f"  stop_reason={response.stop_reason}")

        # Add assistant response to history
        messages.append({"role": "assistant", "content": response.content})

        # Check if done
        if response.stop_reason == "end_turn":
            if verbose:
                print("[agent] Agent finished naturally.")
            break

        # max_tokens: response was truncated mid-generation.  Process any tool
        # calls that were already emitted in the partial response and continue.
        if response.stop_reason not in ("tool_use", "max_tokens"):
            if verbose:
                print(f"[agent] Unexpected stop_reason: {response.stop_reason}. Stopping.")
            break

        # Process tool calls
        tool_results: list[dict] = []
        turn_log: dict[str, Any] = {
            "turn": turn + 1,
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "agent_text": " ".join(
                b.text for b in response.content if b.type == "text"
            ).strip() or None,
            "tool_calls": [],
        }

        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input

            if verbose:
                print(f"  tool_call: {tool_name}({json.dumps(tool_input)[:120]})")

            result = dispatch_tool(session, tool_name, tool_input)

            if verbose:
                result_str = json.dumps(result)
                print(f"  tool_result: {result_str[:200]}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
            turn_log["tool_calls"].append({
                "tool": tool_name,
                "input": tool_input,
                "result": result,
            })

        log["turns"].append(turn_log)

        # Stall detection: max_tokens with no tool calls = model wrote >16384 tokens
        # of planning text without issuing any tool call (common for Opus at large N).
        # Log the stall but do NOT nudge — letting the model fail is the correct
        # benchmark behaviour; stalling at large N is itself a finding.
        if response.stop_reason == "max_tokens" and not tool_results:
            if verbose:
                print("[agent] Stall detected (max_tokens, no tool calls).")
            turn_log["stall"] = True

        # Add tool results to history (empty list if stalled — loop will retry naturally)
        messages.append({"role": "user", "content": tool_results})

        # Check budget
        remaining = session.budget - session.budget_used
        if remaining <= 0:
            if verbose:
                print("[agent] Budget exhausted.")
            messages.append({
                "role": "user",
                "content": "Budget exhausted. Please submit your predictions and hypothesis now.",
            })
            # Allow up to 5 cleanup turns for free tools (submit_prediction, etc.)
            for cleanup_turn in range(5):
                response = _with_retry(
                    client.messages.create, _anthropic_retryable,
                    model=model,
                    max_tokens=16384,
                    system=system_prompt,
                    tools=active_tools,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})
                final_turn_log: dict[str, Any] = {
                    "turn": turn + 2 + cleanup_turn,
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "agent_text": " ".join(
                        b.text for b in response.content if b.type == "text"
                    ).strip() or None,
                    "tool_calls": [],
                    "note": "budget-exhausted cleanup turn",
                }
                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type != "tool_use":
                            continue
                        result = dispatch_tool(session, block.name, block.input)
                        if verbose:
                            print(f"  [cleanup] {block.name} → {json.dumps(result)[:120]}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                        final_turn_log["tool_calls"].append({
                            "tool": block.name,
                            "input": block.input,
                            "result": result,
                        })
                    if tool_results:
                        messages.append({"role": "user", "content": tool_results})
                log["turns"].append(final_turn_log)
                if response.stop_reason != "tool_use":
                    break
            break

    # Embed ground truth gene→phenotype network for diagnostic reports
    gene_id_to_name = {g.id: g.name for g in session.organism.genes}
    gt_edges = []
    for p in session.organism.phenotypes:
        for gene_id, weight in zip(p.readout.depends_on, p.readout.weights):
            if abs(weight) > 0.1:
                gt_edges.append({
                    "from": gene_id_to_name.get(gene_id, gene_id),
                    "to": p.label,
                    "direction": "activates" if weight > 0 else "inhibits",
                    "weight": round(abs(float(weight)), 3),
                })
    log["metadata"]["ground_truth"] = {"gene_phenotype_edges": gt_edges}

    summary = session.get_summary()
    log["summary"] = summary

    if verbose:
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(json.dumps(summary, indent=2))

    if log_path:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(log, f, indent=2)
        if verbose:
            print(f"[agent] Log saved → {log_path}")

    return summary


# ---------------------------------------------------------------------------
# OpenAI agent loop
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# OpenAI agent loop
# ---------------------------------------------------------------------------


def _run_agent_openai(
    session: ExperimentSession,
    model: str = "gpt-5.1",
    max_turns: int = 50,
    verbose: bool = True,
    disease_mode: bool | None = None,
    log_path: str | None = None,
    active_tasks: frozenset[str] | None = None,
    max_tokens_per_turn: int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """
    Run an OpenAI model on a Lemonoids ExperimentSession.

    Requires OPENAI_API_KEY in the environment.
    disease_mode: if None, auto-detected from session.is_disease.
    log_path: if provided, write a structured JSON log to this path.
    active_tasks: subset of {"predict", "diagnose", "rescue"} (default: all).
    Returns the session summary after the agent finishes or budget is exhausted.
    """
    import datetime, os
    from openai import OpenAI, APITimeoutError as OAITimeoutError, APIConnectionError as OAIConnectionError, RateLimitError as OAIRateLimitError

    client_kwargs: dict[str, Any] = {"timeout": _API_TIMEOUT}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    if api_key is not None:
        client_kwargs["api_key"] = api_key
    client = OpenAI(**client_kwargs)
    _openai_retryable = (OAITimeoutError, OAIConnectionError, OAIRateLimitError)

    if disease_mode is None:
        disease_mode = session.is_disease
    if active_tasks is None:
        active_tasks = frozenset({"predict", "diagnose", "rescue"})

    active_tools = _to_openai_tools(_active_tool_list(disease_mode, active_tasks))
    system_prompt = _build_system_prompt(disease_mode, active_tasks)

    # ── Log initialisation ────────────────────────────────────────────────
    log: dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "model": display_name or model,
            "organism_id": session.organism.id,
            "seed": session.organism.seed,
            "n_genes": len(session.organism.genes),
            "budget": session.budget,
            "disease_mode": disease_mode,
            "active_tasks": sorted(active_tasks),
            "generation_commit": _git_commit(),
            "system_prompt_hash": _prompt_hash(system_prompt),
            "max_tokens_per_turn": max_tokens_per_turn or 16384,
            "max_turns": max_turns,
        },
        "turns": [],
        "summary": None,
    }

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if disease_mode:
        messages.append({
            "role": "user",
            "content": (
                "A diseased cell has been prepared for analysis. "
                "Its regulatory network has malfunctioned, producing aberrant phenotypes. "
                "Your task is to identify the malfunction, design rescue interventions, "
                "predict the phenotype tasks, and submit your hypothesis. "
                "Budget is limited — reason carefully. Begin."
            ),
        })
    else:
        messages.append({
            "role": "user",
            "content": (
                "A new synthetic organism has been prepared for you. "
                "Your task is to probe it with experiments, predict the given phenotype tasks, "
                "and submit your best hypothesis about its regulatory structure. "
                "Budget is limited — reason carefully. Begin."
            ),
        })

    def _run_turn(msgs: list[dict]) -> Any:
        kwargs: dict[str, Any] = dict(
            model=model,
            tools=active_tools,
            tool_choice="auto",
            messages=msgs,
        )
        if max_tokens_per_turn is not None:
            # gpt-5.1+ requires max_completion_tokens; older models accept max_tokens.
            # max_completion_tokens is accepted by all current OpenAI chat models.
            kwargs["max_completion_tokens"] = max_tokens_per_turn
        return _with_retry(client.chat.completions.create, _openai_retryable, **kwargs)

    def _process_tool_calls(response_message, turn_log: dict) -> list[dict]:
        """Dispatch all tool calls and return tool result messages."""
        result_messages = []
        for tc in response_message.tool_calls or []:
            tool_name = tc.function.name
            try:
                tool_input = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_input = {}

            if verbose:
                print(f"  tool_call: {tool_name}({json.dumps(tool_input)[:120]})")

            result = dispatch_tool(session, tool_name, tool_input)

            if verbose:
                print(f"  tool_result: {json.dumps(result)[:200]}")

            result_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })
            turn_log["tool_calls"].append({
                "tool": tool_name,
                "input": tool_input,
                "result": result,
            })
        return result_messages

    for turn in range(max_turns):
        if verbose:
            print(f"\n[turn {turn + 1}/{max_turns}] Calling {model}...")

        response = _run_turn(messages)
        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if verbose:
            print(f"  finish_reason={finish_reason}")

        messages.append(msg)

        if finish_reason == "stop":
            # Check whether the session is actually complete before accepting a stop.
            # Some models (e.g. gpt-5.1) occasionally return finish_reason=stop early
            # without submitting predictions/hypothesis. If work is unfinished, inject
            # a nudge and continue rather than silently producing a null record.
            n_tasks = len(session._tasks) if "predict" in session._active_tasks else 0
            n_submitted = len(session._prediction_results)
            tasks_done = n_submitted >= n_tasks
            hypothesis_done = (
                "predict" not in session._active_tasks or session._hypothesis is not None
            )
            if tasks_done and hypothesis_done:
                if verbose:
                    print("[agent] Agent finished naturally.")
                break
            # Unfinished — nudge the model to complete
            missing = []
            if not tasks_done:
                missing.append(f"predictions ({n_submitted}/{n_tasks} submitted)")
            if not hypothesis_done:
                missing.append("hypothesis")
            print(
                f"[agent] finish_reason=stop on turn {turn + 1} but session incomplete "
                f"({', '.join(missing)} missing). Injecting recovery prompt."
            )
            messages.append({
                "role": "user",
                "content": (
                    "You stopped before completing the session. "
                    f"Please finish: {', '.join(missing)}. "
                    "Call get_next_prediction_task() if you haven't yet, then submit_prediction() "
                    "for each task, and finally submit_hypothesis()."
                ),
            })
            continue

        if finish_reason == "length":
            # Context window hit — inject a recovery message and keep going
            print(f"[agent] finish_reason=length on turn {turn + 1}, injecting recovery prompt.")
            messages.append({
                "role": "user",
                "content": (
                    "Your last response was cut off due to length. "
                    "Please continue: submit any remaining predictions and your hypothesis now."
                ),
            })
            continue

        if finish_reason != "tool_calls":
            if verbose:
                print(f"[agent] Unexpected finish_reason: {finish_reason}. Stopping.")
            break

        turn_log: dict[str, Any] = {
            "turn": turn + 1,
            "stop_reason": finish_reason,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "agent_text": msg.content or None,
            "tool_calls": [],
        }
        tool_result_messages = _process_tool_calls(msg, turn_log)
        messages.extend(tool_result_messages)
        log["turns"].append(turn_log)

        # Check budget
        remaining = session.budget - session.budget_used
        if 0 < remaining <= 5:
            messages.append({
                "role": "user",
                "content": (
                    f"WARNING: Only {remaining} budget unit(s) remaining. "
                    "Stop running experiments. Call get_next_prediction_task() now "
                    "and submit your predictions, then submit_hypothesis()."
                ),
            })
        if remaining <= 0:
            if verbose:
                print("[agent] Budget exhausted.")
            messages.append({
                "role": "user",
                "content": "Budget exhausted. Please submit your predictions and hypothesis now.",
            })
            # Allow up to 5 cleanup turns (free tools: get_next_prediction_task,
            # submit_prediction, submit_hypothesis, submit_malfunction_hypothesis)
            for cleanup_turn in range(5):
                response = _run_turn(messages)
                msg = response.choices[0].message
                messages.append(msg)
                final_turn_log: dict[str, Any] = {
                    "turn": turn + 2 + cleanup_turn,
                    "stop_reason": response.choices[0].finish_reason,
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "agent_text": msg.content or None,
                    "tool_calls": [],
                    "note": "budget-exhausted cleanup turn",
                }
                if response.choices[0].finish_reason == "tool_calls":
                    tool_result_messages = _process_tool_calls(msg, final_turn_log)
                    messages.extend(tool_result_messages)
                log["turns"].append(final_turn_log)
                if response.choices[0].finish_reason != "tool_calls":
                    break
            break

    # Embed ground truth gene→phenotype network for diagnostic reports
    gene_id_to_name = {g.id: g.name for g in session.organism.genes}
    gt_edges = []
    for p in session.organism.phenotypes:
        for gene_id, weight in zip(p.readout.depends_on, p.readout.weights):
            if abs(weight) > 0.1:
                gt_edges.append({
                    "from": gene_id_to_name.get(gene_id, gene_id),
                    "to": p.label,
                    "direction": "activates" if weight > 0 else "inhibits",
                    "weight": round(abs(float(weight)), 3),
                })
    log["metadata"]["ground_truth"] = {"gene_phenotype_edges": gt_edges}

    summary = session.get_summary()
    log["summary"] = summary

    if verbose:
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(json.dumps(summary, indent=2))

    if log_path:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(log, f, indent=2)
        if verbose:
            print(f"[agent] Log saved → {log_path}")

    return summary

# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

_ANTHROPIC_PREFIXES = ("claude-",)
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")

# Together AI — OpenAI-compatible endpoint for open-source models.
# Keys: short display name used in --model / results / logs.
# Values: full model ID on Together's platform.
_TOGETHER_MODELS: dict[str, str] = {
    "llama-4-maverick": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
    "deepseek-v3": "deepseek-ai/DeepSeek-V3",
    "qwen-2.5-72b": "Qwen/Qwen2.5-72B-Instruct",
}
_TOGETHER_BASE_URL = "https://api.together.xyz/v1"
_TOGETHER_API_KEY_ENV = "TOGETHER_API_KEY"


def run_agent(
    session: ExperimentSession,
    model: str = "claude-opus-4-6",
    max_turns: int = 50,
    verbose: bool = True,
    disease_mode: bool | None = None,
    log_path: str | None = None,
    active_tasks: frozenset[str] | None = None,
    max_tokens_per_turn: int | None = None,
) -> dict[str, Any]:
    """
    Run an LLM agent on a Lemonoids ExperimentSession.

    Automatically routes to the correct provider based on the model name:
    - claude-*                        → Anthropic API  (requires ANTHROPIC_API_KEY)
    - gpt-* / o1 / o3 / o4           → OpenAI API     (requires OPENAI_API_KEY)
    - llama-4-maverick / deepseek-v3  → Together AI    (requires TOGETHER_API_KEY)
      / qwen-2.5-72b

    Args:
        session:      An ExperimentSession wrapping a generated organism.
        model:        Model identifier, e.g. "claude-opus-4-6" or "gpt-5.1".
        max_turns:    Maximum agent turns before forcing a summary.
        verbose:      Print turn-by-turn progress to stdout.
        disease_mode: Override disease mode detection (default: auto).
        log_path:     Optional path to write a structured JSON session log.
        active_tasks: Subset of {"predict", "diagnose", "rescue"} controlling
                      which task components the agent is asked to complete
                      (default: all three). E.g. frozenset({"predict"}) for
                      predict-only runs.

    Returns:
        Session summary dict from ExperimentSession.get_summary().
    """
    if any(model.startswith(p) for p in _ANTHROPIC_PREFIXES):
        return _run_agent_anthropic(session, model, max_turns, verbose, disease_mode, log_path, active_tasks, max_tokens_per_turn)
    if any(model.startswith(p) for p in _OPENAI_PREFIXES):
        return _run_agent_openai(session, model, max_turns, verbose, disease_mode, log_path, active_tasks, max_tokens_per_turn)
    if model in _TOGETHER_MODELS:
        import os
        api_key = os.environ.get(_TOGETHER_API_KEY_ENV)
        if not api_key:
            raise EnvironmentError(
                f"{_TOGETHER_API_KEY_ENV} not set. Required for model {model!r}."
            )
        return _run_agent_openai(
            session,
            model=_TOGETHER_MODELS[model],
            max_turns=max_turns,
            verbose=verbose,
            disease_mode=disease_mode,
            log_path=log_path,
            active_tasks=active_tasks,
            max_tokens_per_turn=max_tokens_per_turn,
            base_url=_TOGETHER_BASE_URL,
            api_key=api_key,
            display_name=model,
        )
    raise ValueError(
        f"Cannot infer provider from model name {model!r}. "
        "Use a model name starting with 'claude-' (Anthropic) or 'gpt-'/'o1'/'o3' (OpenAI), "
        f"or one of the Together AI models: {list(_TOGETHER_MODELS.keys())}."
    )
