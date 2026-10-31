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
