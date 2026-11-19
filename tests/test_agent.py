"""Tests for agent routing and tool dispatch."""
import json
import pytest
from luca import generate_organism, generate_disease_organism, ExperimentSession
from luca.agent import run_agent, dispatch_tool, _ANTHROPIC_PREFIXES, _OPENAI_PREFIXES
import luca.agent as agent_module


# ---------------------------------------------------------------------------
# Minimal fake Anthropic client, for testing _run_agent_anthropic's
# multi-turn completion logic without a real API call. No such
# infrastructure existed before the seam-bug audit (2026-08-20) — routing
# tests above avoid mocking entirely, letting real (failing, unauthed) API
# calls happen and only checking the failure isn't a routing error.
# ---------------------------------------------------------------------------


class _FakeUsage:
    def __init__(self):
        self.input_tokens = 10
        self.output_tokens = 10
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, call_id, name, input_):
        self.id = call_id
        self.name = name
        self.input = input_


class _FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        if not self._responses:
            raise AssertionError("fake Anthropic client ran out of scripted responses")
        return self._responses.pop(0)


class _FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


def _fake_anthropic(monkeypatch, responses):
    """Patch luca.agent.anthropic.Anthropic to return a scripted fake client."""
    monkeypatch.setattr(
        agent_module.anthropic, "Anthropic",
        lambda *a, **kw: _FakeAnthropicClient(responses),
    )


# ---------------------------------------------------------------------------
# Minimal fake OpenAI-compatible client, mirroring the Anthropic fakes above.
# Added 2026-08-21 to reproduce the OpenRouter empty-choices failure found
# during the qwen/deepseek backfill.
# ---------------------------------------------------------------------------


class _FakeOAIUsage:
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 5


class _FakeOAIFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = json.dumps(arguments)


class _FakeOAIToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeOAIFunction(name, arguments)


class _FakeOAIMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeOAIChoice:
    def __init__(self, message, finish_reason):
        self.message = message
        self.finish_reason = finish_reason


class _FakeOAIResponse:
    def __init__(self, choices):
        self.choices = choices
        self.usage = _FakeOAIUsage()


class _FakeOAIEmptyResponse:
    """Mimics OpenRouter returning HTTP 200 with choices=None when the
    underlying provider fails mid-request — no exception, just a
    well-formed envelope with nothing usable in it."""
    def __init__(self):
        self.choices = None
        self.usage = None


class _FakeOAICompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if not self._responses:
            raise AssertionError("fake OpenAI client ran out of scripted responses")
        return self._responses.pop(0)


class _FakeOAIClient:
    def __init__(self, responses):
        self.chat = type("_Chat", (), {"completions": _FakeOAICompletions(responses)})()


def _fake_openai(monkeypatch, responses):
    """Patch openai.OpenAI to return a scripted fake client. _run_agent_openai
    does `from openai import OpenAI` at call time, which re-reads this
    attribute off the already-imported module — patching it here is enough."""
    fake_client = _FakeOAIClient(responses)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(agent_module, "_API_RETRY_WAIT", 0)  # don't sleep in tests
    return fake_client


def test_run_agent_routes_anthropic():
    from luca.agent import _run_agent_anthropic
    # run_agent with a claude- model should call _run_agent_anthropic
    # We verify routing without making API calls by checking ValueError is NOT raised
    # and that an ImportError/AuthError would come from the provider, not from routing
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    # Should route without raising ValueError
    try:
        run_agent(session, model="claude-opus-4-6", max_turns=1)
    except Exception as e:
        assert "Cannot infer provider" not in str(e), f"Routing failed: {e}"


def test_run_agent_routes_openai():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    try:
        run_agent(session, model="gpt-5.1", max_turns=1)
    except Exception as e:
        assert "Cannot infer provider" not in str(e), f"Routing failed: {e}"


def test_run_agent_unknown_model_raises():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    with pytest.raises(ValueError, match="Cannot infer provider"):
        run_agent(session, model="llama-3-70b")


def test_dispatch_tool_get_organism_info():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    result = dispatch_tool(session, "get_organism_info", {})
    assert "gene_names" in result
    assert "observable_phenotypes" in result


def test_dispatch_tool_run_experiment():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    gene = session.get_info()["gene_names"][0]
    result = dispatch_tool(session, "run_experiment", {"interventions": {gene: {"type": "BLOCK"}}})
    assert "phenotypes" in result


def test_dispatch_tool_run_experiment_json_string():
    """Agent sometimes serializes interventions as a JSON string — should be unwrapped."""
    import json
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    gene = session.get_info()["gene_names"][0]
    interventions_str = json.dumps({gene: {"type": "BLOCK"}})
    result = dispatch_tool(session, "run_experiment", {"interventions": interventions_str})
    assert "phenotypes" in result


def test_dispatch_tool_submit_network_json_string_edges():
    """Model sometimes serializes edges as a JSON string — should be
    unwrapped, mirroring run_experiment's existing JSON-string handling.

    Regression test for seam-bug audit item 3 (real case found in
    experiments/paper_v1/logs/C_easy_disease/logs/qwen-3.5_seed0003.json:
    edges arrived as a JSON string, dispatch_tool iterated over its
    characters, producing 5 nonsense "must be a dict" errors before the
    model retried with a correct list on the next turn)."""
    import json
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    gene = session.get_info()["gene_names"][0]
    phenotype = session.get_info()["observable_phenotypes"][0]
    edges_str = json.dumps([{"gene": gene, "phenotype": phenotype, "direction": "activates"}])
    result = dispatch_tool(session, "submit_network", {"edges": edges_str})
    assert "error" not in result, result
    assert result["n_edges"] == 1


def test_dispatch_tool_submit_network_single_dict_edge():
    """Model sometimes sends a single edge dict instead of a one-item
    list — should be wrapped, not iterated key-by-key.

    Regression test for seam-bug audit item 3 (real case found in
    experiments/paper_v1/logs/C_hard_disease/logs/qwen-3.5_seed0019.json:
    edges was a bare dict, dispatch_tool iterated over its 3 keys,
    producing 3 nonsense "must be a dict" errors before the model
    retried with a correct list on the next turn)."""
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    gene = session.get_info()["gene_names"][0]
    phenotype = session.get_info()["observable_phenotypes"][0]
    edge = {"gene": gene, "phenotype": phenotype, "direction": "activates"}
    result = dispatch_tool(session, "submit_network", {"edges": edge})
    assert "error" not in result, result
    assert result["n_edges"] == 1


def test_dispatch_tool_unknown():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    result = dispatch_tool(session, "nonexistent_tool", {})
    assert "error" in result


def test_run_agent_routes_openrouter_deepseek():
    """deepseek-v3 routes to OpenRouter (switched from Together AI
    2026-08-21, after Together removed serverless access for this
    model)."""
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    try:
        run_agent(session, model="deepseek-v3", max_turns=1)
    except Exception as e:
        assert "Cannot infer provider" not in str(e), f"Routing failed: {e}"


def test_run_agent_routes_openrouter_qwen():
    """qwen-3.5 routes to OpenRouter (switched from Together AI
    2026-08-21, after Together removed serverless access for this
    model)."""
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    try:
        run_agent(session, model="qwen-3.5", max_turns=1)
    except Exception as e:
        assert "Cannot infer provider" not in str(e), f"Routing failed: {e}"


def test_openai_loop_retries_empty_choices_response(monkeypatch):
    """Regression test, found 2026-08-21 during the qwen/deepseek OpenRouter
    backfill: a real qwen-3.5 call on C_easy_disease seed 12 crashed with
    'NoneType' object is not subscriptable at `response.choices[0]`.

    OpenRouter can return HTTP 200 with `choices: null` when the
    underlying provider fails mid-request, instead of an HTTP error the
    SDK would raise on. Before this fix, nothing caught that shape and it
    crashed the whole session outright. It must be retried like any other
    transient provider failure, not treated as a hard error.
    """
    org = generate_disease_organism(difficulty="easy", seed=0)
    m = org.malfunctions[0]
    session = ExperimentSession(org, budget=10, active_tasks=frozenset({"diagnose"}))

    responses = [
        _FakeOAIEmptyResponse(),  # OpenRouter-style upstream failure
        _FakeOAIResponse([_FakeOAIChoice(
            _FakeOAIMessage(tool_calls=[_FakeOAIToolCall(
                "c1", "submit_malfunction_hypothesis",
                {"target_name": m.target_name, "malfunction_type": m.type},
            )]),
            "tool_calls",
        )]),
        _FakeOAIResponse([_FakeOAIChoice(_FakeOAIMessage(content="Done."), "stop")]),
    ]
    fake_client = _fake_openai(monkeypatch, responses)

    agent_module._run_agent_openai(
        session, model="qwen-3.5", max_turns=10, verbose=False,
        disease_mode=True, active_tasks=frozenset({"diagnose"}),
    )

    assert fake_client.chat.completions.calls == 3, (
        "expected one retried call after the empty-choices response, then one more to finish"
    )
    assert session._hypothesis_locked is True


def test_anthropic_loop_requires_malfunction_lock_before_end_turn(monkeypatch):
    """Regression test for seam-bug audit item 1 (2026-08-20).

    Mirrors the fixed OpenAI hypothesis-commit bug (PR #140) for the
    Anthropic loop: stop_reason="end_turn" must not be accepted as "done"
    in disease+diagnose mode until submit_malfunction_hypothesis() has
    locked a scored hypothesis. A free-text submit_hypothesis() call is
    not enough — before this fix, _run_agent_anthropic had no such check
    at all (any end_turn broke the loop unconditionally).
    """
    org = generate_disease_organism(difficulty="easy", seed=0)
    m = org.malfunctions[0]
    session = ExperimentSession(org, budget=10)

    responses = [
        # Turn 1: writes a free-text hypothesis, keeps going (tool_use).
        _FakeResponse("tool_use", [_FakeToolUseBlock("c1", "submit_hypothesis", {"text": "my guess"})]),
        # Turn 2: stops without ever locking a scored hypothesis.
        _FakeResponse("end_turn", [_FakeTextBlock("I'm done.")]),
        # Nudged — turn 3: now locks the real, scored hypothesis.
        _FakeResponse("tool_use", [_FakeToolUseBlock(
            "c2", "submit_malfunction_hypothesis",
            {"target_name": m.target_name, "malfunction_type": m.type},
        )]),
        # Turn 4: stops again, now legitimately done.
        _FakeResponse("end_turn", [_FakeTextBlock("Done for real.")]),
    ]
    _fake_anthropic(monkeypatch, responses)

    agent_module._run_agent_anthropic(
        session, model="claude-opus-4-6", max_turns=10, verbose=False,
        disease_mode=True, active_tasks=frozenset({"diagnose"}),
        use_prompt_cache=False,
    )

    assert session._hypothesis_locked is True, (
        "Anthropic loop accepted end_turn as complete before the "
        "malfunction hypothesis was ever locked"
    )


def test_anthropic_loop_accepts_end_turn_once_hypothesis_locked(monkeypatch):
    """The happy path must still take exactly one end_turn to finish —
    the fix above must not turn every completion into an extra round trip."""
    org = generate_disease_organism(difficulty="easy", seed=0)
    m = org.malfunctions[0]
    session = ExperimentSession(org, budget=10)

    responses = [
        _FakeResponse("tool_use", [_FakeToolUseBlock(
            "c1", "submit_malfunction_hypothesis",
            {"target_name": m.target_name, "malfunction_type": m.type},
        )]),
        _FakeResponse("end_turn", [_FakeTextBlock("Done.")]),
    ]
    _fake_anthropic(monkeypatch, responses)

    agent_module._run_agent_anthropic(
        session, model="claude-opus-4-6", max_turns=10, verbose=False,
        disease_mode=True, active_tasks=frozenset({"diagnose"}),
        use_prompt_cache=False,
    )

    assert session._hypothesis_locked is True


# ---------------------------------------------------------------------------
# The held-out rule has to reach the agent, not only the engine.
#
# Issue 1's fix makes run_experiment and test_rescue refuse a revealed task's
# exact combination. An agent that was never told this spends a turn
# discovering it.
# ---------------------------------------------------------------------------

def _tool(tools, name):
    return next(t for t in tools if t["name"] == name)


def test_run_experiment_tool_states_the_held_out_rule():
    from luca.agent import TOOLS
    assert "held out" in _tool(TOOLS, "run_experiment")["description"].lower()


def test_prediction_task_tool_states_that_one_answer_is_scored():
    from luca.agent import TOOLS
    description = _tool(TOOLS, "submit_prediction")["description"].lower()
    assert "once" in description or "one answer" in description


# ---------------------------------------------------------------------------
# Issue 13 — the tool layer billed GPT for experiments it never ran
#
# dispatch_tool read only the "interventions" and "gene_interventions" keys.
# gpt-4.1, gpt-4o and gpt-5.1 often sent the flat form {"G001": "BLOCK"} with
# no wrapper, which reached the engine as {}. The engine simulated the
# unperturbed organism, charged one unit of budget and returned a normal
# success result. No error was returned, so the model never learned and
# repeated the format for the whole session.
#
# Measured over the 1,220 stored session logs, of 18,356 run_experiment and
# test_rescue calls: 1,450 used the flat form and 85 carried no payload at
# all. Both shapes came only from gpt-4o, gpt-4.1, gpt-5.1 and qwen-3.5;
# claude-opus-4-6, claude-sonnet-4-6 and deepseek-v3 sent 9,008 calls between
# them and never used either.
#
# These tests assert the intervention REACHES THE ENGINE, not merely that the
# call returned without an error. Asserting `"phenotypes" in result` passes
# against the bug, which is exactly how it survived.
# ---------------------------------------------------------------------------

def _healthy_dispatch_session(budget=5):
    session = ExperimentSession(generate_organism(seed=0), budget=budget, seed=0)
    return session.get_info()["gene_names"][0], session


class TestFlatInterventionsReachTheEngine:

    def test_flat_payload_is_applied(self):
        gene, session = _healthy_dispatch_session()
        dispatch_tool(session, "run_experiment", {gene: "BLOCK"})
        applied = session._experiment_log[-1]["interventions"]
        assert applied != {}, "the tool layer discarded the interventions"
        assert gene in applied

    def test_flat_form_matches_the_canonical_form(self):
        """Same seed and same budget_used draw the same RNG, so any
        difference is the tool layer, not noise."""
        gene, flat_session = _healthy_dispatch_session()
        _, wrapped_session = _healthy_dispatch_session()
        flat = dispatch_tool(flat_session, "run_experiment", {gene: "BLOCK"})
        wrapped = dispatch_tool(
            wrapped_session, "run_experiment", {"interventions": {gene: {"type": "BLOCK"}}}
        )
        assert "error" not in flat
        assert flat["phenotypes"] == wrapped["phenotypes"]

    def test_flat_payload_with_dict_values_is_applied(self):
        gene, session = _healthy_dispatch_session()
        dispatch_tool(session, "run_experiment", {gene: {"type": "BLOCK"}})
        assert gene in session._experiment_log[-1]["interventions"]

    def test_a_wrapper_key_wins_over_stray_top_level_keys(self):
        """The flat-form fallback must not override an explicit key."""
        _gene, session = _healthy_dispatch_session()
        names = session.get_info()["gene_names"]
        wanted, stray = names[0], names[1]
        dispatch_tool(
            session, "run_experiment",
            {"interventions": {wanted: {"type": "BLOCK"}}, stray: "BOOST"},
        )
        applied = session._experiment_log[-1]["interventions"]
        assert wanted in applied
        assert stray not in applied

    def test_rescue_applies_a_flat_payload(self):
        """test_rescue read one key name only, so it was narrower still.

        Seed 1 is a LOCK_LO fault on G014, so BOOST rescues it. This seed is
        chosen because it DISCRIMINATES: an empty rescue scores 0.0 here. On
        many seeds an empty rescue already scores 1.0 — the organism recovers
        on its own — and a comparison there would pass against the bug while
        proving nothing.
        """
        def rescue_with(tool_input):
            session = ExperimentSession(
                generate_disease_organism(seed=1), budget=5, seed=1
            )
            dispatch_tool(session, "submit_malfunction_hypothesis",
                          {"target_name": "G014", "malfunction_type": "LOCK_LO"})
            return dispatch_tool(session, "test_rescue", tool_input)

        nothing = rescue_with({"interventions": {}})
        wrapped = rescue_with({"interventions": {"G014": {"type": "BOOST"}}})
        flat = rescue_with({"G014": "BOOST"})
        alt_key = rescue_with({"gene_interventions": {"G014": {"type": "BOOST"}}})

        assert nothing["restored_fraction"] == 0.0, (
            "this seed must not rescue itself, or the test proves nothing")
        assert wrapped["restored_fraction"] == 1.0
        assert flat["restored_fraction"] == wrapped["restored_fraction"]
        assert alt_key["restored_fraction"] == wrapped["restored_fraction"]


class TestUnreadablePayloadsAreRefused:
    """An experiment either applies what was asked, or says why it did not."""

    def test_payload_with_no_recognisable_target_is_refused(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"foo": "bar"})
        assert "error" in result
        assert session.budget_used == 0

    def test_missing_payload_is_refused(self):
        """An absent interventions key is a malformed call, not a null
        experiment. 85 stored calls carried no payload; every one came from a
        model that also sent the flat form, and the agent text beside them
        announces an intervention it then failed to send."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {})
        assert "error" in result
        assert session.budget_used == 0

    def test_explicit_empty_interventions_still_runs(self):
        """{"interventions": {}} is a deliberate null experiment."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": {}})
        assert "error" not in result
        assert session.budget_used == 1

    def test_non_mapping_value_is_refused_not_emptied(self):
        """_normalise_interventions turned anything it could not read into {}."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": 42})
        assert "error" in result
        assert session.budget_used == 0

    def test_list_form_with_no_readable_item_is_refused(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(
            session, "run_experiment", {"interventions": [{"nonsense": 1}]}
        )
        assert "error" in result
        assert session.budget_used == 0

    def test_list_form_with_one_unreadable_item_is_refused(self):
        """A partial drop corrupts the session the same way a full one does."""
        gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": [
            {"gene": gene, "type": "BLOCK"},
            {"gene": "G002", "type": "NONSENSE"},
        ]})
        assert "error" in result
        assert session.budget_used == 0

    def test_list_form_that_reads_cleanly_is_applied(self):
        gene, session = _healthy_dispatch_session()
        dispatch_tool(session, "run_experiment", {"interventions": [
            {"gene": gene, "type": "BLOCK"},
        ]})
        assert gene in session._experiment_log[-1]["interventions"]

    def test_rescue_refuses_an_unreadable_payload(self):
        session = ExperimentSession(
            generate_disease_organism(seed=1), budget=5, seed=1
        )
        dispatch_tool(session, "submit_malfunction_hypothesis",
                      {"target_name": "G014", "malfunction_type": "LOCK_LO"})
        before = session.budget_used
        result = dispatch_tool(session, "test_rescue", {"foo": "bar"})
        assert "error" in result
        assert session.budget_used == before


# ---------------------------------------------------------------------------
# Review of the issue 13 fix. Measured over the 1,220 stored session logs, of
# 18,356 run_experiment and test_rescue calls.
# ---------------------------------------------------------------------------

def _disease_dispatch_session(budget=5):
    org = generate_disease_organism(seed=0, difficulty="medium")
    return ExperimentSession(org, budget=budget, seed=0)


class TestRefusalNamesTheDocumentedShape:
    """Finding 2. 472 stored calls sent an alternative container name, such as
    {"BLOCK": ["G001"]} or {"perturbations": {...}}. Every one of them ran as
    an empty experiment and was billed; none returned an error. They are now
    refused, which is correct, but the message named only the stray key. A
    model cannot correct itself from that."""

    def test_unknown_target_error_names_the_wrapper_key(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"BLOCK": ["G001"]})
        assert "error" in result
        assert "BLOCK" in result["error"]
        assert "interventions" in result["error"], (
            "the message must name the key the model should have used"
        )

    def test_the_refusal_still_costs_no_budget(self):
        _gene, session = _healthy_dispatch_session()
        dispatch_tool(session, "run_experiment", {"perturbations": {"G001": "BLOCK"}})
        assert session.budget_used == 0


class TestWrapperKeyEdgeCases:

    def test_a_null_wrapper_falls_through_to_the_alternate_key(self):
        """Finding 3. The old code used `or`, so a null primary key fell
        through. The key-presence loop stopped that. No stored call sent a
        null wrapper, but the old behaviour was correct and is restored."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {
            "interventions": None,
            "gene_interventions": {"G001": {"type": "BLOCK"}},
        })
        assert "error" not in result, result
        assert "G001" in session._experiment_log[-1]["interventions"]

    def test_an_empty_list_payload_is_refused(self):
        """Finding 4. All four stored empty-list calls were
        {"interventions": [], "signals": [...]} — a signal-only experiment.
        Each one ran as a null experiment and was billed. An empty list
        carries no genes, so it is refused like a missing key."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": []})
        assert "error" in result
        assert session.budget_used == 0

    def test_an_explicit_empty_map_is_still_a_null_experiment(self):
        """The guard. {"interventions": {}} stays deliberate."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": {}})
        assert "error" not in result
        assert session.budget_used == 1


class TestRescueStateErrorsComeFirst:
    """Finding 5. The payload check ran before the session saw the call, so a
    malformed payload masked the two state errors. The agent fixed the
    payload, resent, and only then learned the real blocker. That costs a turn
    each time."""

    def test_the_missing_hypothesis_error_wins(self):
        session = _disease_dispatch_session()
        result = dispatch_tool(session, "test_rescue", {})
        assert "error" in result
        assert "submit_malfunction_hypothesis" in result["error"]

    def test_the_healthy_organism_error_wins(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "test_rescue", {})
        assert "error" in result
        assert "not a disease organism" in result["error"]

    def test_a_malformed_payload_is_still_refused_once_the_state_is_right(self):
        session = _disease_dispatch_session()
        dispatch_tool(session, "submit_malfunction_hypothesis",
                      {"target_name": "G014", "malfunction_type": "LOCK_LO"})
        result = dispatch_tool(session, "test_rescue", {})
        assert "error" in result
        assert "interventions" in result["error"]
        assert session.budget_used == 0


class TestMalformedListEntriesAreRefusedNotRaised:
    """Review finding 1. The guards covered `item` and `action` but not
    `target`, so an unhashable target reached `normalised[target]` and raised
    TypeError. dispatch_tool is called bare, so one malformed list ended the
    whole session. 'Refused, not emptied' must not become 'crashed'."""

    def test_an_unhashable_target_is_refused(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {
            "interventions": [{"gene": ["G001"], "type": "BLOCK"}]
        })
        assert "error" in result
        assert session.budget_used == 0

    def test_a_numeric_target_is_refused(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {
            "interventions": [{"gene": 7, "type": "BLOCK"}]
        })
        assert "error" in result

    def test_a_readable_entry_beside_an_unhashable_one_is_still_refused(self):
        """The partial case: a session must not run on fewer genes than the
        model believes."""
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {
            "interventions": [
                {"gene": "G001", "type": "BLOCK"},
                {"gene": ["G002"], "type": "BOOST"},
            ]
        })
        assert "error" in result
        assert session.budget_used == 0


class TestRefusalsDoNotAdviseANoOp:
    """Review finding 2. The empty-list refusal told the model to send
    {"interventions": {"wave-X": "activate"}}. Every signal in seed 0 makes
    that bit-identical to a null experiment, because `activate` resolves to the
    strength the simulator already uses (issue 5). The four stored empty-list
    calls were signal-only requests, so that advice would send exactly the
    wrong audience into a billed no-op — the failure issue 13 removes."""

    def test_the_empty_list_refusal_does_not_promise_signal_support(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": []})
        assert "error" in result
        assert "activate" not in result["error"], (
            "a signal activation is a no-op today; see issues 5 and 18"
        )

    def test_the_empty_list_refusal_names_the_deliberate_null_form(self):
        _gene, session = _healthy_dispatch_session()
        result = dispatch_tool(session, "run_experiment", {"interventions": []})
        assert '{"interventions": {}}' in result["error"]
