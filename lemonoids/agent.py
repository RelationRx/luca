"""Claude agent harness for Lemonoids reasoning benchmark."""
from __future__ import annotations

import json
from typing import Any

import anthropic

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
            "Provide a map of phenotype label → predicted value (0.0 to 1.0). "
            "Returns MSE and accuracy (fraction within 0.15 threshold)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID from the prediction tasks list (e.g. 'task_00').",
                },
                "prediction": {
                    "type": "object",
                    "description": "Map of phenotype label → predicted float value [0.0, 1.0].",
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
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a computational biologist studying a *de novo* synthetic organism.

CRITICAL: All gene names (e.g. G001, G042), signal labels (e.g. "nutrient-X"), and phenotype \
names (e.g. "growth-rate") are INVENTED VOCABULARY. They do NOT correspond to any real \
biological system. Prior biological knowledge is IRRELEVANT and may mislead you. \
The only valid path to understanding this organism is systematic causal reasoning \
from perturbation experiments.

PRIMARY GOALS (in order of importance):
1. Phenotype prediction — accurately predict phenotype outcomes under novel multi-gene \
interventions. This requires building a real causal model, not guessing.
2. Causal hypothesis — submit a concise, evidence-based hypothesis naming which genes \
regulate which phenotypes and how.

WORKFLOW:
1. Call get_organism_info() to understand the gene set, signals, phenotypes, and baseline.
2. Run perturbation experiments (BLOCK, BOOST, DAMPEN, signal activations) to map gene→phenotype \
causal relationships. Focus on genes that move phenotypes; note direction and magnitude.
3. When you have a working causal model, call get_next_prediction_task() to receive \
one prediction task at a time. Submit your prediction via submit_prediction(), \
then call get_next_prediction_task() again for the next task.
4. Submit your final causal hypothesis via submit_hypothesis().

Strategy tips:
- Single-gene BLOCK/BOOST experiments first — identify which genes affect which phenotypes.
- BLOCK and BOOST of the same gene producing opposite phenotype shifts is strong causal evidence.
- Budget is limited — build your model before requesting prediction tasks.
- Prediction tasks involve two simultaneous cross-module interventions. Reason from \
your model: predict each phenotype based on the combined effect of both genes.
- Do not guess 0.5 — every prediction should be grounded in experimental evidence.

Always call get_organism_info() first."""

DISEASE_SYSTEM_PROMPT = """You are a computational biologist studying a *de novo* synthetic organism \
that is exhibiting a diseased state.

CRITICAL: All gene names (e.g. G001, G042), signal labels (e.g. "nutrient-X"), and phenotype \
names (e.g. "growth-rate") are INVENTED VOCABULARY. They do NOT correspond to any real \
biological system. Prior biological knowledge is IRRELEVANT and may mislead you. \
The only valid path to understanding this organism is systematic causal reasoning \
from perturbation experiments.

DISEASE CONTEXT: This cell exhibits aberrant phenotypes compared to its healthy baseline ranges. \
The regulatory network has a single malfunction — either a node locked high (LOCK_HI), a node \
locked low (LOCK_LO), or a persistently active external signal (PERSIST). Your job is to identify \
it and restore healthy phenotypes.

PRIMARY GOALS (in order of importance):
1. Malfunction diagnosis — identify which gene or signal is broken and how \
(LOCK_HI / LOCK_LO / PERSIST). Submit via submit_malfunction_hypothesis().
2. Rescue — design an intervention that restores aberrant phenotypes to healthy ranges. \
Test it via test_rescue().
3. Phenotype prediction — accurately predict phenotype outcomes under novel multi-gene \
interventions. Call get_next_prediction_task() when ready, one task at a time.
4. Causal hypothesis — submit a concise explanation of the malfunction and regulatory logic.

WORKFLOW:
1. Call get_organism_info() to see which phenotypes are aberrant and their healthy ranges.
2. Run experiments targeting genes that affect the aberrant phenotypes to localise the fault.
3. When confident, submit your malfunction hypothesis via submit_malfunction_hypothesis(). \
This is a one-time, irreversible commitment — it locks immediately and unlocks test_rescue(). \
Score is revealed at session end, not now.
4. Test rescue interventions with test_rescue() (costs 1 budget each).
5. Call get_next_prediction_task() for prediction tasks — one at a time; submit each \
via submit_prediction() before the next unlocks.
6. Submit a final hypothesis via submit_hypothesis().

Strategy tips:
- LOCK_HI (node locked high): BLOCK or DAMPEN of that node should reduce the overactive phenotypes.
- LOCK_LO (node locked low): BOOST of that node should restore under-active phenotypes.
- PERSIST (signal persistently active): the signal is always on — BLOCK of its direct targets may help.
- Aberrant phenotypes are your compass — focus experiments on genes that move them.
- Budget is limited — prioritise experiments that maximally disambiguate the malfunction.
- Commit to your hypothesis only when the evidence is clear — you cannot revise it.

Always call get_organism_info() first."""

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
# Tool dispatch
# ---------------------------------------------------------------------------


def dispatch_tool(session: ExperimentSession, tool_name: str, tool_input: dict) -> Any:
    """Route a tool call to the session."""
    if tool_name == "get_organism_info":
        return session.get_info()
    elif tool_name == "get_next_prediction_task":
        return session.get_next_prediction_task()
    elif tool_name == "run_experiment":
        interventions = tool_input.get("interventions", {})
        # Claude sometimes serializes the dict as a JSON string — unwrap it
        if isinstance(interventions, str):
            try:
                interventions = json.loads(interventions)
            except json.JSONDecodeError:
                return {"error": f"interventions must be an object, got string: {interventions!r}"}
        return session.run_experiment(interventions)
    elif tool_name == "submit_prediction":
        return session.submit_prediction(
            tool_input["task_id"],
            tool_input["prediction"],
        )
    elif tool_name == "submit_hypothesis":
        return session.submit_hypothesis(tool_input["text"])
    elif tool_name == "test_rescue":
        interventions = tool_input.get("interventions", {})
        if isinstance(interventions, str):
            try:
                interventions = json.loads(interventions)
            except json.JSONDecodeError:
                return {"error": f"interventions must be an object, got string: {interventions!r}"}
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


def run_agent(
    session: ExperimentSession,
    model: str = "claude-opus-4-6",
    max_turns: int = 50,
    verbose: bool = True,
    disease_mode: bool | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    """
    Run the Claude agent on a Lemonoids ExperimentSession.

    disease_mode: if None, auto-detected from session._is_disease.
    log_path: if provided, write a structured JSON log to this path.
    Returns the session summary after the agent finishes or budget is exhausted.
    """
    import datetime, os
    client = anthropic.Anthropic()

    if disease_mode is None:
        disease_mode = session._is_disease

    active_tools = TOOLS + DISEASE_TOOLS if disease_mode else TOOLS
    system_prompt = DISEASE_SYSTEM_PROMPT if disease_mode else SYSTEM_PROMPT

    # ── Log initialisation ────────────────────────────────────────────────
    log: dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "organism_id": session.organism.id,
            "seed": session.organism.seed,
            "budget": session.budget,
            "disease_mode": disease_mode,
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

        response = client.messages.create(
            model=model,
            max_tokens=4096,
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

        if response.stop_reason != "tool_use":
            if verbose:
                print(f"[agent] Unexpected stop_reason: {response.stop_reason}. Stopping.")
            break

        # Process tool calls
        tool_results: list[dict] = []
        turn_log: dict[str, Any] = {
            "turn": turn + 1,
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

        # Add tool results to history
        messages.append({"role": "user", "content": tool_results})

        # Check budget
        remaining = session.budget - session.budget_used
        if remaining <= 0:
            if verbose:
                print("[agent] Budget exhausted.")
            # Give agent one more turn to submit predictions/hypothesis
            messages.append({
                "role": "user",
                "content": "Budget exhausted. Please submit your predictions and hypothesis now.",
            })
            # One final turn
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=active_tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})
            final_turn_log: dict[str, Any] = {
                "turn": turn + 2,   # one past the last main turn
                "agent_text": " ".join(
                    b.text for b in response.content if b.type == "text"
                ).strip() or None,
                "tool_calls": [],
                "note": "budget-exhausted final turn",
            }
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    result = dispatch_tool(session, block.name, block.input)
                    if verbose:
                        print(f"  [final] {block.name} → {json.dumps(result)[:120]}")
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


def run_agent_openai(
    session: ExperimentSession,
    model: str = "gpt-5.1",
    max_turns: int = 50,
    verbose: bool = True,
    disease_mode: bool | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    """
    Run an OpenAI model as agent on a Lemonoids ExperimentSession.

    Requires OPENAI_API_KEY in the environment.
    disease_mode: if None, auto-detected from session._is_disease.
    log_path: if provided, write a structured JSON log to this path.
    Returns the session summary after the agent finishes or budget is exhausted.
    """
    import datetime, os
    from openai import OpenAI

    client = OpenAI()

    if disease_mode is None:
        disease_mode = session._is_disease

    active_tools = _to_openai_tools(TOOLS + DISEASE_TOOLS if disease_mode else TOOLS)
    system_prompt = DISEASE_SYSTEM_PROMPT if disease_mode else SYSTEM_PROMPT

    # ── Log initialisation ────────────────────────────────────────────────
    log: dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "organism_id": session.organism.id,
            "seed": session.organism.seed,
            "budget": session.budget,
            "disease_mode": disease_mode,
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
        return client.chat.completions.create(
            model=model,
            tools=active_tools,
            tool_choice="auto",
            messages=msgs,
        )

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
            if verbose:
                print("[agent] Agent finished naturally.")
            break

        if finish_reason != "tool_calls":
            if verbose:
                print(f"[agent] Unexpected finish_reason: {finish_reason}. Stopping.")
            break

        turn_log: dict[str, Any] = {
            "turn": turn + 1,
            "agent_text": msg.content or None,
            "tool_calls": [],
        }
        tool_result_messages = _process_tool_calls(msg, turn_log)
        messages.extend(tool_result_messages)
        log["turns"].append(turn_log)

        # Check budget
        remaining = session.budget - session.budget_used
        if remaining <= 0:
            if verbose:
                print("[agent] Budget exhausted.")
            messages.append({
                "role": "user",
                "content": "Budget exhausted. Please submit your predictions and hypothesis now.",
            })
            response = _run_turn(messages)
            msg = response.choices[0].message
            messages.append(msg)
            final_turn_log: dict[str, Any] = {
                "turn": turn + 2,
                "agent_text": msg.content or None,
                "tool_calls": [],
                "note": "budget-exhausted final turn",
            }
            if response.choices[0].finish_reason == "tool_calls":
                tool_result_messages = _process_tool_calls(msg, final_turn_log)
                messages.extend(tool_result_messages)
            log["turns"].append(final_turn_log)
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
