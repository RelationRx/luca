"""How an intervention payload is found inside a tool call.

**One source of truth, on purpose.** The tool layer reads a call to decide what
the engine runs. `report.py` reads the same call to tell a human what ran. When
those two disagree, the trace stops describing the session. Issue 13 taught
this the hard way: the tool layer learned to apply the flat form
``{"G001": "BLOCK"}`` while `report.py` kept reading the ``interventions`` key
alone, so a flat experiment ran in the engine and then vanished from the trace
and from edge inference. Both modules now call `intervention_payload`.
"""
from __future__ import annotations

from typing import Any

# run_experiment and test_rescue take the same payload. A model may send the
# intervention map under either key, or — issue 13 — unwrapped at the top level.
INTERVENTION_WRAPPER_KEYS = ("interventions", "gene_interventions")


MISSING_INTERVENTIONS_ERROR = (
    "Missing required parameter 'interventions'. Send "
    '{"interventions": {"G001": {"type": "BLOCK"}}}. For a deliberate '
    'null experiment send {"interventions": {}} explicitly.'
)


def flat_form_hint(stray_key: str) -> str:
    """The sentence appended when a flat-form guess hit an unknown target.

    Measured over the 1,220 stored session logs: 472 calls sent an alternative
    container name rather than the documented one, such as ``{"BLOCK":
    ["G001"]}``, ``{"perturbations": {...}}`` or ``{"genes": {"G001":
    "BLOCK"}}``. Every one of them ran as an empty experiment and was billed;
    not one returned an error. They are refused now, which is correct, but a
    refusal that names only the stray key leaves the model no way to correct
    itself. None of the 18,356 calls carried a commentary key such as
    ``reasoning``, so a stray key is nearly always a container the model
    invented.
    """
    return (
        f" '{stray_key}' is not a gene or a signal. If it was meant to hold "
        f'the interventions, send them under "interventions": '
        f'{{"interventions": {{"G001": {{"type": "BLOCK"}}}}}}.'
    )


def intervention_payload(tool_input: dict) -> tuple[Any | None, bool]:
    """Find the interventions in a tool call, whatever shape the model used.

    Returns ``(payload, used_flat_fallback)``.

    **Issue 13.** The tool layer used to read two key names and nothing else,
    so a model that sent its targets at the top level of ``tool_input`` — with
    no wrapper key at all — had its whole experiment replaced by ``{}``. The
    engine then simulated an untouched organism, charged a unit of budget and
    returned a normal-looking success. The model never learned, so it repeated
    the format for the rest of the session.

    Measured over the 1,220 stored session logs, of 18,356 run_experiment and
    test_rescue calls: 1,450 used the flat form and 85 carried no payload at
    all. gpt-4.1 alone sent 872 flat calls in 2,001.

    A wrapper key wins whenever one is present, including when it is empty:
    ``{"interventions": {}}`` means a deliberate null experiment, not an
    invitation to read the rest of the call as genes.

    A wrapper key whose value is ``None`` is skipped rather than honoured. The
    original code used ``or``, which fell through a null value to the alternate
    key; the key-presence test stopped that. No stored call sent a null
    wrapper, but a null is the absence of a payload, not an empty one.

    Returns ``(None, False)`` when the call carries no payload at all. That is
    refused by the caller rather than silently run as an empty experiment:
    every one of the 85 empty calls came from a model that also sent the flat
    form, and the agent text beside them announces an intervention that was
    then not sent.

    A payload may legitimately be a JSON string, so the return type carries no
    error channel — ``None`` is the only non-payload value.
    """
    for key in INTERVENTION_WRAPPER_KEYS:
        if tool_input.get(key) is not None:
            return tool_input[key], False

    if any(key in tool_input for key in INTERVENTION_WRAPPER_KEYS):
        # Every wrapper key present held null. A null is an absent payload,
        # not an empty one, so it is refused rather than read as a flat form.
        return None, False

    if not tool_input:
        return None, False

    # Flat form: the payload is the intervention map. An unknown target is
    # rejected by the session, which costs no budget.
    return tool_input, True
