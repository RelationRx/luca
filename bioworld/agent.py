"""Claude agent harness for BioWorld reasoning benchmark."""
from __future__ import annotations

import json
from typing import Any

import anthropic

from .experiment import ExperimentSession

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "get_organism_info",
        "description": (
            "Retrieve information about the synthetic organism: gene names, available signals, "
            "observable phenotypes, budget, baseline phenotype values, and prediction tasks. "
            "This call is free (no budget cost)."
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
            "Specify gene interventions (KO=knockout, OE=overexpress, KD=knockdown) "
            "and/or signal activations. Returns phenotype readouts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "interventions": {
                    "type": "object",
                    "description": (
                        "Map of target → intervention. Targets can be gene names (e.g. 'G001') "
                        "with values like {\"type\": \"KO\"}, {\"type\": \"OE\"}, {\"type\": \"KD\"}, "
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
        "name": "submit_module_assignment",
        "description": (
            "Submit your hypothesis about which genes belong to which functional modules. "
            "No budget cost. Returns ARI and NMI scores vs ground truth. "
            "Module names can be arbitrary strings you invent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assignments": {
                    "type": "object",
                    "description": "Map of gene_name → module_label (e.g. {'G001': 'module-A', 'G002': 'module-B'}).",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["assignments"],
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

CRITICAL: All gene names (e.g. G001, G042), module labels (e.g. "ion-flux-regulator"), signal \
labels (e.g. "nutrient-X"), and phenotype names (e.g. "growth-rate") are INVENTED VOCABULARY. \
They do NOT correspond to any real biological system. Prior biological knowledge is \
IRRELEVANT and may mislead you. The only valid path to understanding this organism is \
systematic causal reasoning from perturbation experiments.

Your goal:
1. Use run_experiment() to probe the organism with gene knockouts (KO), overexpression (OE), \
knockdowns (KD), and signal activations.
2. Build a causal model of which genes regulate which phenotypes.
3. Predict phenotype values for the given prediction tasks.
4. Optionally, group genes into functional modules based on co-regulation patterns.
5. Submit a hypothesis summarizing your causal model.

Strategy tips:
- Start with single-gene KO/OE experiments to identify phenotype-affecting genes.
- Look for genes where KO and OE produce opposite phenotype changes (causal evidence).
- Budget is limited — plan your experiments efficiently.
- Submit predictions even with partial evidence; use 0.5 as a neutral prior.

Always call get_organism_info() first to understand the setup."""

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def dispatch_tool(session: ExperimentSession, tool_name: str, tool_input: dict) -> Any:
    """Route a tool call to the session."""
    if tool_name == "get_organism_info":
        return session.get_info()
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
    elif tool_name == "submit_module_assignment":
        return session.submit_module_assignment(tool_input["assignments"])
    elif tool_name == "submit_hypothesis":
        return session.submit_hypothesis(tool_input["text"])
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def run_agent(
    session: ExperimentSession,
    model: str = "claude-opus-4-6",
    max_turns: int = 50,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Run the Claude agent on a BioWorld ExperimentSession.

    Returns the session summary after the agent finishes or budget is exhausted.
    """
    client = anthropic.Anthropic()

    messages: list[dict] = []

    # Kick off with a user message
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
            system=SYSTEM_PROMPT,
            tools=TOOLS,
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
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})
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
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
            break

    summary = session.get_summary()
    if verbose:
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(json.dumps(summary, indent=2))
    return summary
