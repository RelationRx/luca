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

import json
from typing import Any

# run_experiment and test_rescue take the same payload. A model may send the
# intervention map under either key, or — issue 13 — unwrapped at the top level.
INTERVENTION_WRAPPER_KEYS = ("interventions", "gene_interventions")

# The engine upper-cases a gene's intervention type (issue 12). A signal action
# stays lower case, because report.py keys its colour on "activate".
GENE_INTERVENTION_TYPES = ("BLOCK", "BOOST", "DAMPEN")

# The key names a model may use inside one list entry, in the order the engine
# reads them. The order is part of the contract: a model that sends both
# "target" and "gene" must perturb the same gene in the engine and in the
# trace. Reversing it here once made the trace name a gene that was never
# perturbed.
ENTRY_TARGET_KEYS = ("target", "gene", "name")
ENTRY_ACTION_KEYS = ("action", "mode", "intervention", "type")


def entry_target(item: Any) -> str | None:
    """The target of one list entry, or None."""
    if not isinstance(item, dict):
        return None
    for key in ENTRY_TARGET_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
        if value:
            return None  # present but unusable: do not fall through to a worse key
    return None


def entry_action(item: Any) -> str | None:
    """The intervention type of one list entry, or None if unreadable."""
    if not isinstance(item, dict):
        return None
    for key in ENTRY_ACTION_KEYS:
        value = item.get(key)
        if not value:
            continue
        if isinstance(value, str) and value.upper() in GENE_INTERVENTION_TYPES:
            return value.upper()
        return None
    return None


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
        f". '{stray_key}' is not a gene or a signal. If it was meant to hold "
        f'the interventions, send them under "interventions": '
        f'{{"interventions": {{"G001": {{"type": "BLOCK"}}}}}}.'
    )


def _decoded(value: Any) -> Any:
    """Unwrap a payload sent as a JSON string.

    Some models send ``{"interventions": "{\"G001\": {\"type\": \"BLOCK\"}}"}``.
    The tool layer decoded that and the engine applied it, but `report.py` did
    not, so the trace raised on a shape the engine ran. The decode belongs here,
    with the rest of the shared reading. A string that is not JSON is returned
    unchanged, so the caller still produces the error.
    """
    for _ in range(4):
        if not isinstance(value, str):
            return value
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def canonical_type(value: Any) -> str:
    """The intervention type of one target, as the engine would read it.

    `_resolve_interventions` upper-cases a gene type, so ``"block"`` and
    ``"BLOCK"`` are the same experiment. A signal action is not a gene type and
    keeps the case it came in, because `report.py` colours ``"activate"`` by
    that exact string.
    """
    text = str(value.get("type", "")) if isinstance(value, dict) else str(value)
    return text.upper() if text.upper() in GENE_INTERVENTION_TYPES else text


def canonical_interventions(raw: Any) -> dict[str, dict]:
    """``{target: {"type": T}}`` for any payload shape, or ``{}``.

    One reading for the engine and the trace. Anything that is not a mapping or
    a list of entries reads as empty rather than raising: the engine refuses
    those shapes now, so they appear in new logs and must still render.
    """
    raw = _decoded(raw)
    if isinstance(raw, list):
        out: dict[str, dict] = {}
        for item in raw:
            target, action = entry_target(item), entry_action(item)
            if target is None or action is None:
                # The engine refuses the whole call when one entry is
                # unreadable, so the trace must not show a partial experiment.
                return {}
            out[target] = {"type": action}
        return out
    if not isinstance(raw, dict):
        return {}
    out = {}
    for target, value in raw.items():
        if isinstance(value, dict):
            inner = value.get("type")
            if not isinstance(inner, str) or not inner:
                continue
            out[str(target)] = {"type": canonical_type(inner)}
        elif isinstance(value, str) and value:
            out[str(target)] = {"type": canonical_type(value)}
        # Anything else is a container the model invented, not a target. 472
        # stored calls sent one; the trace used to draw it as a gene.
    return out


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
    invitation to read the rest of the call as genes. When two wrapper keys are
    present and one is empty, the populated one wins: a model that sent both
    meant the one with genes in it.

    A wrapper key whose value is ``None`` is skipped, and the alternate key is
    read instead. The original code used ``or``, which fell through a null
    value; a key-presence test briefly replaced it and stopped the fall-through,
    which was wrong. No stored call sent a null wrapper, but a null is the
    absence of a payload, not an empty one. When every wrapper key present is
    null, the call is refused rather than read as a flat form.

    Returns ``(None, False)`` when the call carries no payload at all. That is
    refused by the caller rather than silently run as an empty experiment:
    every one of the 85 empty calls came from a model that also sent the flat
    form, and the agent text beside them announces an intervention that was
    then not sent.

    A payload may legitimately be a JSON string, so the return type carries no
    error channel — ``None`` is the only non-payload value.
    """
    tool_input = _decoded(tool_input)
    if not isinstance(tool_input, dict):
        # Some providers hand the whole arguments object over as a string.
        # dispatch_tool does not guard its argument, so raising here ends the
        # session rather than the call.
        return None, False

    present = [k for k in INTERVENTION_WRAPPER_KEYS if tool_input.get(k) is not None]

    # A populated wrapper beats an empty one. The original `or` chain fell
    # through an empty `interventions` to a populated `gene_interventions`; a
    # key-presence rule briefly stopped that, so a model that sent both ran an
    # empty experiment and was billed for it — issue 13 under a new name.
    for key in present:
        value = _decoded(tool_input[key])
        if value:
            return value, False
    if present:
        # Every wrapper present is empty: a deliberate null experiment.
        return _decoded(tool_input[present[0]]), False

    if any(key in tool_input for key in INTERVENTION_WRAPPER_KEYS):
        # Every wrapper key present held null. A null is an absent payload,
        # not an empty one, so it is refused rather than read as a flat form.
        return None, False

    if not tool_input:
        return None, False

    # Flat form: the payload is the intervention map. An unknown target is
    # rejected by the session, which costs no budget.
    return tool_input, True
